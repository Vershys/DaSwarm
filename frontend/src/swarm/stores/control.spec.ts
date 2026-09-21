import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useControl } from './control'
import type { SwarmObject, SwarmEvent } from '../types'

const object: SwarmObject = { id: 'candidate-1', object_type: 'Candidate', title: 'Fixture', status: 'REVIEW_PENDING', version: 2, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-02T00:00:00Z', tags: [], metadata: {} }
const early: SwarmEvent = { sequence: 1, event_id: 'event-1', event_type: 'DISCOVERED', object_id: object.id, timestamp: object.created_at, trace_id: 'trace-1', causation_id: null, payload: {} }
const late: SwarmEvent = { ...early, sequence: 2, event_id: 'event-2', timestamp: object.updated_at }
let responses: Record<string, unknown>
let requests: Array<{path: string; body: unknown}>
class FakeSocket {
  static OPEN = 1
  static CONNECTING = 0
  readyState = 0
  static instances: FakeSocket[] = []
  onopen: (() => void) | null = null
  onclose: (() => void) | null = null
  onmessage: ((message: {data: string}) => void) | null = null
  constructor(public url: string) { FakeSocket.instances.push(this) }
  close() { this.readyState = 3; this.onclose?.() }
  event(sequence: number) { this.onmessage?.({data: JSON.stringify({type: 'swarm.event', sequence, event: {...early, sequence}})}) }
}
beforeEach(() => {
  setActivePinia(createPinia()); requests = []; FakeSocket.instances = []
  responses = {'/config': {version: 1, data: {}, ontology: {queues: [], object_types: []}}, '/objects/query': {items: [object]}, '/graph/neighborhood': {nodes: [object], edges: [], truncated: false, recommended_view: 'graph'}, ['/objects/'+object.id+'/timeline']: [early,late], ['/objects/'+object.id+'/trace']: [early,late], ['/objects/'+object.id]: object}
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace('/api/v1/swarm',''); requests.push({path, body: init?.body ? JSON.parse(String(init.body)) : undefined})
    if (!(path in responses)) throw new Error('Unexpected request '+path)
    return {ok: true, json: async () => responses[path]}
  }))
})
afterEach(() => {useControl().stop(); vi.useRealTimers(); vi.unstubAllGlobals()})
describe('linked swarm state', () => {
  it('propagates one selection to inspector, graph, timeline, and causal trace', async () => {
    const s=useControl(); await s.select({objectId: object.id, objectType: 'Candidate'})
    expect(s.primary?.objectId).toBe(object.id); expect(s.selected).toEqual(object)
    expect(s.graph.nodes[0].id).toBe(object.id); expect(s.timeline).toEqual([early,late]); expect(s.trace).toEqual([early,late])
  })
  it('reconstructs prior selection and blocks writes in replay', async () => {
    const historical={...object,status:'DISCOVERED',version:1}
    responses['/replay/snapshot?at='+encodeURIComponent(early.timestamp)]={objects:[historical]}
    responses['/graph/neighborhood']={nodes:[historical],edges:[],truncated:false,recommended_view:'graph'}
    const s=useControl(); s.primary={objectId:object.id,objectType:'Candidate'}; await s.setTime(early.timestamp)
    expect(s.selected?.status).toBe('DISCOVERED'); expect(s.timeline).toEqual([early]); expect(s.trace).toEqual([early])
    expect(requests.find(r=>r.path==='/graph/neighborhood')?.body).toMatchObject({at:early.timestamp})
    await s.command('discover'); expect(s.error).toContain('Return to LIVE')
    expect(requests.some(r=>r.path==='/commands/execute')).toBe(false)
    expect(object.status).toBe('REVIEW_PENDING')
  })
  it('deduplicates realtime sequences and reconnects from the last cursor', async () => {
    vi.useFakeTimers(); const s=useControl(); await s.start(); const ws=FakeSocket.instances[0]
    ws.onopen?.(); ws.event(4); ws.event(4); ws.event(3)
    expect(s.lastSequence).toBe(4); expect(s.recent).toHaveLength(1)
    ws.close(); await vi.advanceTimersByTimeAsync(1200)
    expect(FakeSocket.instances[1].url).toContain('last_sequence=4')
    FakeSocket.instances[1].event(5); expect(s.recent.map(e=>e.sequence)).toEqual([5,4])
  })
  it('receives live events during replay without replacing historical objects', async () => {
    vi.useFakeTimers(); const s=useControl(); await s.start(); s.mode='REPLAY'; s.objects=[{...object,status:'DISCOVERED'}]
    const count=requests.length; FakeSocket.instances[0].event(7); await vi.advanceTimersByTimeAsync(1000)
    expect(requests).toHaveLength(count); expect(s.objects[0].status).toBe('DISCOVERED'); expect(s.lastSequence).toBe(7)
  })
})
