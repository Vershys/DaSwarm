import { test, expect } from '@playwright/test'

test('A06 A07 A10 A23 live-first UI, linked selection and replay transport',async({page,request})=>{
  const sockets:string[]=[]
  const received:Array<{event?:{object_id:string;event_type:string}}>=[]
  page.on('websocket',socket=>{
    if(!socket.url().includes('/ws/swarm'))return
    sockets.push(socket.url())
    socket.on('framereceived',frame=>{received.push(JSON.parse(String(frame.payload)))})
  })
  const errors:string[]=[]
  page.on('pageerror',e=>errors.push(e.message))

  await page.goto('/swarm')
  await expect(page.locator('.connection')).toContainText('Ready')
  await expect(page.getByText('LIVE',{exact:true})).toBeVisible()
  await expect(page.getByRole('button',{name:'Start Discovery'})).toBeVisible()

  // Acceptance uses an explicit test-only fixture injection so browser evidence
  // is deterministic. The production UI itself exposes only live discovery.
  const title='Browser acceptance '+Date.now()
  const discovered=await page.request.post('/api/v1/swarm/commands/execute',{data:{
    action:'discover',
    idempotency_key:crypto.randomUUID(),
    payload:{title}
  }})
  expect(discovered.ok()).toBeTruthy()
  const result=await discovered.json()

  await expect.poll(async()=>{
    return await page.getByRole('button').filter({hasText:title}).count()
  }).toBeGreaterThan(0)
  await page.getByRole('button').filter({hasText:title}).first().click()
  await expect(page.getByText(title,{exact:true}).last()).toBeVisible()

  const graph=await page.request.post('/api/v1/swarm/graph/neighborhood',{data:{object_id:result.object.id,depth:2,limit:100}})
  expect(graph.ok()).toBeTruthy()
  expect((await graph.json()).edges.length).toBeGreaterThan(0)

  const timeline=await page.request.get('/api/v1/swarm/objects/'+result.object.id+'/timeline')
  const events=await timeline.json()
  const at=events[0].timestamp
  const replay=await page.request.get('/api/v1/swarm/replay/snapshot?at='+encodeURIComponent(at))
  expect(replay.ok()).toBeTruthy()
  const snapshot=await replay.json()
  expect(snapshot.objects.find((o:any)=>o.id===result.object.id)?.status).toBe('DISCOVERED')

  await page.context().setOffline(true)
  await expect(page.locator('.connection')).toContainText('Connecting')

  const gapTitle='Reconnect gap '+Date.now()
  const gap=await request.post('/api/v1/swarm/commands/execute',{data:{
    action:'discover',
    idempotency_key:crypto.randomUUID(),
    payload:{title:gapTitle}
  }})
  expect(gap.ok()).toBeTruthy()
  const gapObject=(await gap.json()).object

  await page.context().setOffline(false)
  await expect(page.locator('.connection')).toContainText('Ready')
  await expect.poll(()=>received.filter(x=>x.event?.object_id===gapObject.id&&x.event?.event_type==='CANDIDATE_DISCOVERED').length).toBe(1)
  expect(sockets.some(url=>Number(new URL(url).searchParams.get('last_sequence'))>0)).toBeTruthy()
  await expect.poll(async()=>await page.getByRole('button').filter({hasText:gapTitle}).count()).toBeGreaterThan(0)

  await page.screenshot({path:'../test-evidence/live-first-swarm.png',fullPage:true})
  expect(errors).toEqual([])
})
