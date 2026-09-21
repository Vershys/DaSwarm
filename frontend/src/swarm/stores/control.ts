import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SwarmObject, ObjectRef, SwarmEvent, Graph } from '../types'
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/v1/swarm'+path, { credentials: 'include', method: body === undefined ? 'GET' : 'POST', headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'}, body: body === undefined ? undefined : JSON.stringify(body) })
  if (!response.ok) { const error = await response.json(); throw new Error(error.detail || `HTTP ${response.status}`) }
  return response.json()
}
export const useControl = defineStore('swarm-control', () => {
  const primary = ref<ObjectRef|null>(null), selected = ref<SwarmObject|null>(null)
  const workspace = ref('Overview'), search = ref(''), objectType = ref(''), status = ref('')
  const mode = ref<'LIVE'|'REPLAY'>('LIVE'), cursor = ref(''), connected = ref(false), lastSequence = ref(0)
  const objects = ref<SwarmObject[]>([]), timeline = ref<SwarmEvent[]>([]), trace = ref<SwarmEvent[]>([])
  const graph = ref<Graph>({nodes:[],edges:[],truncated:false,recommended_view:'graph'})
  const error = ref(''), busy = ref(false), configuration = ref<{version:number;data:Record<string,unknown>;ontology:{queues:string[];object_types:string[]}}|null>(null)
  const recent = ref<SwarmEvent[]>([])
  let socket: WebSocket|null = null, timer: ReturnType<typeof setTimeout>|null = null, stopped = false
  let refreshTimer: ReturnType<typeof setTimeout>|null = null
  async function refresh() {
    try {
      if (mode.value === 'REPLAY') {
        const result = await api<{objects:SwarmObject[]}>('/replay/snapshot?at='+encodeURIComponent(cursor.value))
        objects.value = result.objects.filter(o=>(!objectType.value||o.object_type===objectType.value)&&(!status.value||o.status===status.value)&&o.title.toLowerCase().includes(search.value.toLowerCase()))
      } else objects.value = (await api<{items:SwarmObject[]}>('/objects/query',{object_type:objectType.value||null,search:search.value,status:status.value||null,limit:200})).items
      if (primary.value) await select(primary.value)
    } catch (e) { error.value = String(e) }
  }
  async function select(reference:ObjectRef) {
    primary.value=reference
    const historical = mode.value === 'REPLAY'
    const [g,t,tr] = await Promise.all([
      api<Graph>('/graph/neighborhood',{object_id:reference.objectId,depth:2,limit:100,at:historical?cursor.value:null}),
      api<SwarmEvent[]>('/objects/'+reference.objectId+'/timeline'),
      api<SwarmEvent[]>('/objects/'+reference.objectId+'/trace')
    ])
    graph.value=g
    timeline.value=historical?t.filter(e=>e.timestamp<=cursor.value):t
    trace.value=historical?tr.filter(e=>e.timestamp<=cursor.value):tr
    selected.value=historical?(g.nodes.find(n=>n.id===reference.objectId)||null):await api<SwarmObject>('/objects/'+reference.objectId)
  }
  async function command(action:string,payload:Record<string,unknown>={},configurationCommand=false) {
    if(mode.value!=='LIVE') {error.value='Return to LIVE to change state';return}
    busy.value=true;error.value=''
    try {
      const result=await api<{object?:SwarmObject}>('/commands/execute',{action,payload,object_id:selected.value?.id,expected_version:configurationCommand?configuration.value?.version:selected.value?.version,idempotency_key:crypto.randomUUID(),mode:mode.value})
      if(result.object) primary.value={objectId:result.object.id,objectType:result.object.object_type}
      configuration.value=await api('/config');await refresh()
    } catch(e) {error.value=String(e)} finally {busy.value=false}
  }
  async function setTime(value:string) {cursor.value=value;mode.value=value?'REPLAY':'LIVE';await refresh()}
  function connect() {
    if(stopped)return
    socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/ws/swarm?last_sequence=${lastSequence.value}`)
    socket.onopen=()=>{connected.value=true}
    socket.onmessage=(message)=>{
      const envelope=JSON.parse(message.data)
      if(envelope.type!=='swarm.event'||envelope.sequence<=lastSequence.value)return
      lastSequence.value=envelope.sequence
      recent.value=[envelope.event,...recent.value].slice(0,80)
      if(mode.value==='LIVE'&&!refreshTimer) refreshTimer=setTimeout(()=>{refreshTimer=null;void refresh()},250)
    }
    socket.onclose=()=>{connected.value=false;if(!stopped)timer=setTimeout(connect,1200)}
  }
  async function start() {stopped=false;configuration.value=await api('/config');await refresh();connect()}
  function stop() {stopped=true;socket?.close();if(timer)clearTimeout(timer);if(refreshTimer)clearTimeout(refreshTimer)}
  return {primary,selected,workspace,search,objectType,status,mode,cursor,connected,lastSequence,objects,timeline,trace,graph,error,busy,configuration,recent,refresh,select,command,setTime,start,stop}
})
