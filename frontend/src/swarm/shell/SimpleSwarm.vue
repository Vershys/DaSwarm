<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, useControl } from '../stores/control'
import type { SwarmObject } from '../types'

const s = useControl()

const candidates = ref<SwarmObject[]>([])
const compositions = ref<SwarmObject[]>([])
const posts = ref<SwarmObject[]>([])
const summary = ref<{objects:Record<string,number>;tasks:Record<string,number>;pending_outbox:number;last_sequence:number}|null>(null)
const selected = ref<SwarmObject|null>(null)
const atoms = ref<SwarmObject[]>([])
const storyboard = ref<string[]>([])
const message = ref('')
const actionBusy = ref(false)
const settingsOpen = ref(false)
const settingsSaving = ref(false)
const settingsDraft = ref({
  exploration_fraction: 0.1,
  max_attempts: 5,
  lease_seconds: 30,
  max_duration_seconds: 300,
  max_media_bytes: 100_000_000,
  max_resolution: 3840,
  routing_weights: { semantic_fit: 0.55, novelty: 0.2, quality: 0.25 },
  paused_queues: [] as string[]
})
let poll: ReturnType<typeof setInterval>|undefined

const activeTasks = computed(() => {
  const tasks = summary.value?.tasks || {}
  return Object.entries(tasks)
    .filter(([state]) => !['SUCCEEDED','CANCELLED','DEAD_LETTER'].includes(state))
    .reduce((total,[,count]) => total + Number(count), 0)
})
const systemReady = computed(() => s.connected)
const hasDemo = computed(() => candidates.value.length > 0)
const latestCandidate = computed(() => candidates.value[0] || null)

function statusLabel(o:SwarmObject) {
  const labels:Record<string,string> = {
    DISCOVERED:'Found',
    NORMALIZED:'Preparing',
    DEDUPED:'Checking duplicates',
    ANALYZING:'Analyzing video',
    ANALYZED:'Analysis complete',
    ROUTED:'Ready to build',
    REVIEW_PENDING:'Ready for you',
    SYNTHESIS_QUEUED:'Building clip',
    COMPOSED:'Clip created',
    DRAFT:'Draft',
    RENDER_QUEUED:'Waiting to render',
    RENDERING:'Rendering clip',
    REVIEW:'Ready to review',
    APPROVED:'Approved',
    PUBLISH_QUEUED:'Publishing test post',
    PUBLISHED:'Finished',
    FAILED:'Needs attention'
  }
  return labels[o.status] || o.status.replaceAll('_',' ').toLowerCase()
}

function statusDetail(o:SwarmObject) {
  if (o.object_type === 'Candidate') {
    if (['DISCOVERED','NORMALIZED','DEDUPED','ANALYZING','ANALYZED'].includes(o.status)) return 'The workers are handling this automatically.'
    if (['ROUTED','REVIEW_PENDING','HELD'].includes(o.status)) return 'Analysis is done. You can choose the moments to turn into a clip.'
    if (o.status === 'SYNTHESIS_QUEUED') return 'Your storyboard is in the render pipeline.'
    if (o.status === 'COMPOSED') return 'A composition was created. Open the output below.'
  }
  if (o.object_type === 'Composition') {
    if (['DRAFT','RENDER_QUEUED','RENDERING'].includes(o.status)) return 'The render worker is creating the video.'
    if (o.status === 'REVIEW') return 'Watch the result, then approve or reject it.'
    if (o.status === 'APPROVED') return 'Approved. You can now test the publishing workflow.'
    if (o.status === 'PUBLISHED') return 'The simulated publish flow finished successfully.'
  }
  return 'More technical details are available in Settings when you need them.'
}

function openSettings() {
  const d = s.configuration?.data || {}
  const weights = (d.routing_weights || {}) as Record<string,number>
  settingsDraft.value = {
    exploration_fraction: Number(d.exploration_fraction ?? 0.1),
    max_attempts: Number(d.max_attempts ?? 5),
    lease_seconds: Number(d.lease_seconds ?? 30),
    max_duration_seconds: Number(d.max_duration_seconds ?? 300),
    max_media_bytes: Number(d.max_media_bytes ?? 100_000_000),
    max_resolution: Number(d.max_resolution ?? 3840),
    routing_weights: {
      semantic_fit: Number(weights.semantic_fit ?? 0.55),
      novelty: Number(weights.novelty ?? 0.2),
      quality: Number(weights.quality ?? 0.25)
    },
    paused_queues: Array.isArray(d.paused_queues) ? [...d.paused_queues as string[]] : []
  }
  settingsOpen.value = true
}

async function saveSettings() {
  settingsSaving.value = true
  try {
    await s.command('configure', settingsDraft.value as unknown as Record<string,unknown>, true)
    settingsOpen.value = false
    message.value = 'Settings saved.'
  } catch (e) { message.value = String(e) }
  finally { settingsSaving.value = false }
}

function pipelinePaused(group:string[]) { return group.every(q=>settingsDraft.value.paused_queues.includes(q)) }
function setPipeline(group:string[], paused:boolean) {
  const current = new Set(settingsDraft.value.paused_queues)
  for (const q of group) paused ? current.add(q) : current.delete(q)
  settingsDraft.value.paused_queues = [...current]
}

async function refreshData() {
  try {
    const [c,co,p,ops] = await Promise.all([
      api<{items:SwarmObject[]}>('/objects/query',{object_type:'Candidate',search:'',status:null,limit:20}),
      api<{items:SwarmObject[]}>('/objects/query',{object_type:'Composition',search:'',status:null,limit:20}),
      api<{items:SwarmObject[]}>('/objects/query',{object_type:'Post',search:'',status:null,limit:20}),
      api<{objects:Record<string,number>;tasks:Record<string,number>;pending_outbox:number;last_sequence:number}>('/operations/summary')
    ])
    candidates.value = c.items
    compositions.value = co.items
    posts.value = p.items
    summary.value = ops
    if (selected.value) {
      selected.value = [...c.items,...co.items].find(o => o.id === selected.value?.id) || selected.value
    }
  } catch (e) {
    message.value = String(e)
  }
}

async function choose(o:SwarmObject) {
  selected.value = o
  atoms.value = []
  storyboard.value = []
  try { await s.select({objectId:o.id,objectType:o.object_type,version:o.version}) } catch {}
}

async function runDemo() {
  actionBusy.value = true
  message.value = 'Creating a local test video and handing it to the workers…'
  try {
    await s.command('discover')
    await refreshData()
    const newest = candidates.value[0]
    if (newest) await choose(newest)
    message.value = 'Demo started. The workers will analyze it automatically.'
  } finally {
    actionBusy.value = false
  }
}

async function buildClip(o:SwarmObject) {
  actionBusy.value = true
  message.value = ''
  try {
    await choose(o)
    const result = await api<SwarmObject[]>('/candidates/'+o.id+'/atoms')
    atoms.value = result
    storyboard.value = result.map(a=>a.id)
    if (!result.length) message.value = 'No moments are ready yet. Give the workers a little more time.'
  } catch (e) { message.value=String(e) }
  finally { actionBusy.value=false }
}

function toggleAtom(id:string) {
  storyboard.value = storyboard.value.includes(id)
    ? storyboard.value.filter(x=>x!==id)
    : [...storyboard.value,id]
}

async function renderClip() {
  if (!selected.value || !storyboard.value.length) return
  actionBusy.value = true
  message.value = 'Rendering your selected moments…'
  try {
    await s.command('synthesize',{atom_ids:storyboard.value})
    atoms.value=[]; storyboard.value=[]
    await refreshData()
  } finally { actionBusy.value=false }
}

async function approve(o:SwarmObject) {
  actionBusy.value=true
  try { await choose(o); await s.command('approve'); await refreshData() }
  finally { actionBusy.value=false }
}
async function reject(o:SwarmObject) {
  actionBusy.value=true
  try { await choose(o); await s.command('reject'); await refreshData() }
  finally { actionBusy.value=false }
}
async function publish(o:SwarmObject) {
  actionBusy.value=true
  message.value='Running the simulated publishing workflow…'
  try { await choose(o); await s.command('publish'); await refreshData() }
  finally { actionBusy.value=false }
}

onMounted(async()=>{ try { await s.start(); await refreshData(); poll=setInterval(()=>void refreshData(),2000) } catch(e) { message.value=String(e) } })
onUnmounted(()=>{ s.stop(); if(poll) clearInterval(poll) })
</script>

<template>
  <div class="simple-app">
    <header class="simple-header">
      <div class="brand"><span class="mark">M</span><div><strong>DaSwarm</strong><small>Content swarm control</small></div></div>
      <div class="header-actions">
        <span class="connection" :class="{ready:systemReady}">● {{systemReady?'Ready':'Connecting'}}</span>
        <span class="simulation">LOCAL SIMULATION</span>
        <button @click="openSettings">Settings</button>
      </div>
    </header>

    <main>
      <section class="hero">
        <div>
          <p class="eyebrow">SYSTEM STATUS</p>
          <h1>{{systemReady?'DaSwarm is ready.':'DaSwarm is starting…'}}</h1>
          <p class="lead">Start a job, watch it move through the workers, then review the result. Technical controls stay out of the way unless you ask for them.</p>
        </div>
        <div class="health">
          <div><strong>{{activeTasks}}</strong><span>jobs working</span></div>
          <div><strong>{{candidates.length}}</strong><span>videos found</span></div>
          <div><strong>{{compositions.length}}</strong><span>clips built</span></div>
          <div><strong>{{posts.length}}</strong><span>test posts</span></div>
        </div>
      </section>

      <section class="start-grid">
        <article class="action-card primary-card">
          <span class="step">AVAILABLE NOW</span>
          <h2>Test the whole pipeline</h2>
          <p>DaSwarm generates a harmless local sample video, then runs normalization, duplicate checking, analysis, clipping and routing.</p>
          <button class="primary" :disabled="!systemReady||actionBusy" @click="runDemo">{{actionBusy?'Working…':'Run Demo'}}</button>
          <small>This does <b>not</b> search the internet or publish anything real.</small>
        </article>
        <article class="action-card disabled-card">
          <span class="step">NEXT CAPABILITY</span>
          <h2>Discover videos on the internet</h2>
          <p>Browser/source adapters will continuously find real videos and feed them into the same pipeline.</p>
          <button disabled>Internet Discovery — Not installed yet</button>
          <small>The UI will enable this automatically when a real discovery provider is installed.</small>
        </article>
      </section>

      <div v-if="message || s.error" class="notice" :class="{error:!!s.error}">
        <span>{{s.error || message}}</span><button v-if="s.error" @click="s.error=''">Dismiss</button>
      </div>

      <section class="workflow">
        <div class="section-heading"><div><p class="eyebrow">HOW IT WORKS</p><h2>Four simple stages</h2></div><span>{{activeTasks ? 'Workers are active' : (hasDemo ? 'Waiting for your next action' : 'Ready to begin')}}</span></div>
        <div class="steps">
          <div><b>1</b><strong>Find</strong><span>Bring a video into DaSwarm.</span></div>
          <div><b>2</b><strong>Understand</strong><span>Workers analyze, deduplicate and break it into useful moments.</span></div>
          <div><b>3</b><strong>Build</strong><span>Choose moments and render a new composition.</span></div>
          <div><b>4</b><strong>Review</strong><span>Approve the result and test the publish workflow.</span></div>
        </div>
      </section>

      <section class="work-area">
        <div class="section-heading">
          <div><p class="eyebrow">YOUR WORK</p><h2>{{latestCandidate?'Current videos':'Nothing here yet'}}</h2></div>
          <button class="quiet" @click="refreshData">Refresh</button>
        </div>
        <div v-if="!candidates.length" class="empty">
          <strong>No videos have entered the pipeline.</strong>
          <span>Press <b>Run Demo</b> above to see the full system work once.</span>
        </div>
        <div v-else class="items">
          <button v-for="o in candidates" :key="o.id" class="item" :class="{selected:selected?.id===o.id}" @click="choose(o)">
            <div><strong>{{o.title}}</strong><span>Video · {{statusLabel(o)}}</span></div>
            <span class="pill">{{statusLabel(o)}}</span>
          </button>
        </div>

        <article v-if="selected?.object_type==='Candidate'" class="next-action">
          <div><p class="eyebrow">SELECTED VIDEO</p><h3>{{selected.title}}</h3><p>{{statusDetail(selected)}}</p></div>
          <button v-if="['ROUTED','REVIEW_PENDING','HELD','COMPOSED'].includes(selected.status)" class="primary" :disabled="actionBusy" @click="buildClip(selected)">Choose moments</button>
          <span v-else class="working">{{['FAILED','ARCHIVED'].includes(selected.status)?'Open Settings for technical details':'● Workers are processing this automatically'}}</span>
        </article>

        <div v-if="atoms.length" class="storyboard">
          <div><p class="eyebrow">BUILD YOUR CLIP</p><h3>Choose the moments to keep</h3><p>They will play in the order shown below.</p></div>
          <button v-for="a in atoms" :key="a.id" :class="{chosen:storyboard.includes(a.id)}" @click="toggleAtom(a.id)">
            <span>{{storyboard.includes(a.id)?storyboard.indexOf(a.id)+1:'—'}}</span>
            <div><strong>{{String(a.metadata.motif||'Moment')}}</strong><small>{{a.metadata.start}}–{{a.metadata.end}} seconds</small></div>
          </button>
          <button class="primary render" :disabled="!storyboard.length||actionBusy" @click="renderClip">Render selected moments</button>
        </div>
      </section>

      <section v-if="compositions.length" class="outputs">
        <div class="section-heading"><div><p class="eyebrow">OUTPUTS</p><h2>Clips to review</h2></div></div>
        <article v-for="o in compositions" :key="o.id" class="output-card">
          <div><strong>{{o.title}}</strong><span>{{statusLabel(o)}}</span><p>{{statusDetail(o)}}</p></div>
          <div class="output-actions">
            <button v-if="o.status==='REVIEW'" class="primary" :disabled="actionBusy" @click="approve(o)">Approve</button>
            <button v-if="o.status==='REVIEW'" :disabled="actionBusy" @click="reject(o)">Reject</button>
            <button v-if="o.status==='APPROVED'" class="primary" :disabled="actionBusy" @click="publish(o)">Publish test post</button>
            <span v-if="['RENDER_QUEUED','RENDERING','PUBLISH_QUEUED'].includes(o.status)" class="working">● Working automatically</span>
            <span v-if="o.status==='PUBLISHED'" class="done">✓ Finished</span>
          </div>
        </article>
      </section>
    </main>

    <div v-if="settingsOpen" class="settings-backdrop" @click.self="settingsOpen=false">
      <section class="settings-panel">
        <div class="settings-heading">
          <div><p class="eyebrow">CONFIGURATION</p><h2>DaSwarm settings</h2><p>Defaults are already usable. Change these only when you want different behavior.</p></div>
          <button @click="settingsOpen=false">Close</button>
        </div>

        <div class="setting-section">
          <h3>Discovery behavior</h3>
          <label>Explore vs. focus <strong>{{Math.round(settingsDraft.exploration_fraction*100)}}% explore</strong>
            <input v-model.number="settingsDraft.exploration_fraction" type="range" min="0" max="1" step="0.05">
          </label>
          <p>Higher values spend more effort looking outside what already fits well.</p>
        </div>

        <div class="setting-section">
          <h3>How videos are matched</h3>
          <div class="triple">
            <label>Topic fit<input v-model.number="settingsDraft.routing_weights.semantic_fit" type="number" min="0" max="1" step="0.05"></label>
            <label>Novelty<input v-model.number="settingsDraft.routing_weights.novelty" type="number" min="0" max="1" step="0.05"></label>
            <label>Quality<input v-model.number="settingsDraft.routing_weights.quality" type="number" min="0" max="1" step="0.05"></label>
          </div>
        </div>

        <div class="setting-section">
          <h3>Content limits</h3>
          <div class="triple">
            <label>Max video length (sec)<input v-model.number="settingsDraft.max_duration_seconds" type="number" min="1"></label>
            <label>Max resolution<input v-model.number="settingsDraft.max_resolution" type="number" min="1"></label>
            <label>Max file size (MB)<input :value="Math.round(settingsDraft.max_media_bytes/1000000)" type="number" min="1" @input="settingsDraft.max_media_bytes=Number(($event.target as HTMLInputElement).value)*1000000"></label>
          </div>
        </div>

        <div class="setting-section">
          <h3>Processing controls</h3>
          <div class="switch-row"><span><strong>Discovery</strong><small>Finding and fetching new items</small></span><button @click="setPipeline(['DISCOVER','FETCH_METADATA'],!pipelinePaused(['DISCOVER','FETCH_METADATA']))">{{pipelinePaused(['DISCOVER','FETCH_METADATA'])?'Resume':'Pause'}}</button></div>
          <div class="switch-row"><span><strong>Analysis</strong><small>Understanding, deduplicating and routing</small></span><button @click="setPipeline(['NORMALIZE','DEDUPLICATE','ANALYZE_TEXT','ANALYZE_VIDEO','EMBED','TRANSCRIBE','ATOMIZE','CLUSTER','ROUTE'],!pipelinePaused(['NORMALIZE','DEDUPLICATE','ANALYZE_TEXT','ANALYZE_VIDEO','EMBED','TRANSCRIBE','ATOMIZE','CLUSTER','ROUTE']))">{{pipelinePaused(['NORMALIZE','DEDUPLICATE','ANALYZE_TEXT','ANALYZE_VIDEO','EMBED','TRANSCRIBE','ATOMIZE','CLUSTER','ROUTE'])?'Resume':'Pause'}}</button></div>
          <div class="switch-row"><span><strong>Creation</strong><small>Composing and rendering clips</small></span><button @click="setPipeline(['COMPOSE','RENDER','REVIEW'],!pipelinePaused(['COMPOSE','RENDER','REVIEW']))">{{pipelinePaused(['COMPOSE','RENDER','REVIEW'])?'Resume':'Pause'}}</button></div>
          <div class="switch-row"><span><strong>Publishing</strong><small>Publishing, metrics and learning</small></span><button @click="setPipeline(['PUBLISH','COLLECT_METRICS','UPDATE_MODEL'],!pipelinePaused(['PUBLISH','COLLECT_METRICS','UPDATE_MODEL']))">{{pipelinePaused(['PUBLISH','COLLECT_METRICS','UPDATE_MODEL'])?'Resume':'Pause'}}</button></div>
        </div>

        <details class="technical">
          <summary>Technical reliability options</summary>
          <div class="triple tech-grid">
            <label>Retry attempts<input v-model.number="settingsDraft.max_attempts" type="number" min="1" max="20"></label>
            <label>Worker lease (sec)<input v-model.number="settingsDraft.lease_seconds" type="number" min="1" max="3600"></label>
          </div>
          <p>These affect task recovery and worker fencing. Most users should leave them at their defaults.</p>
        </details>

        <div class="settings-footer">
          <button @click="settingsOpen=false">Cancel</button>
          <button class="primary" :disabled="settingsSaving" @click="saveSettings">{{settingsSaving?'Saving…':'Save settings'}}</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.simple-app{min-height:100vh;background:#0c1219;color:#dce6ef;font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}.simple-header{height:70px;border-bottom:1px solid #263341;background:#121b25;display:flex;align-items:center;justify-content:space-between;padding:0 34px;position:sticky;top:0;z-index:10}.brand{display:flex;align-items:center;gap:12px}.brand .mark{display:grid;place-items:center;width:34px;height:34px;border:1px solid #6bd8ee;color:#6bd8ee;font-weight:800}.brand strong{display:block;font-size:16px}.brand small{display:block;color:#8396a8;font-size:11px}.header-actions{display:flex;align-items:center;gap:12px}.connection{font:11px monospace;color:#d69b60}.connection.ready{color:#73d0a7}.simulation{font:10px monospace;color:#80a0b8;background:#172532;padding:5px 8px;border-radius:4px}.simple-app button{cursor:pointer;background:#1b2835;border:1px solid #33485a;color:#d4e2ed;border-radius:6px;padding:9px 13px;font:inherit}.simple-app button:hover:not(:disabled){border-color:#6bd8ee;background:#233847}.simple-app button:disabled{opacity:.5;cursor:not-allowed}.simple-app button.primary{background:#15536a;border-color:#2e88a5;color:#d8f8ff;font-weight:650}.simple-app main{max-width:1180px;margin:0 auto;padding:48px 28px 80px}.hero{display:grid;grid-template-columns:1.35fr 1fr;gap:42px;align-items:end;margin-bottom:34px}.eyebrow{margin:0 0 7px;color:#6f91a9;font:10px monospace;letter-spacing:1.4px;font-weight:700}.hero h1{font-size:36px;line-height:1.15;margin:0 0 14px;font-weight:600;letter-spacing:-1px}.lead{max-width:660px;color:#98aabd;font-size:15px}.health{display:grid;grid-template-columns:repeat(2,1fr);border:1px solid #273644;border-radius:8px;background:#111a24}.health div{padding:16px;border-right:1px solid #273644;border-bottom:1px solid #273644}.health div:nth-child(2n){border-right:0}.health div:nth-last-child(-n+2){border-bottom:0}.health strong{font-size:24px;font-weight:500;display:block}.health span{font-size:11px;color:#8296a8}.start-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:34px}.action-card{border:1px solid #2a3947;background:#121c26;padding:24px;border-radius:8px}.primary-card{border-color:#346576}.disabled-card{opacity:.78}.step{font:10px monospace;color:#79b9cf}.action-card h2,.workflow h2,.work-area h2,.outputs h2{margin:7px 0 8px;font-size:20px;font-weight:550}.action-card p{color:#91a5b6;min-height:44px}.action-card button{display:block;margin:18px 0 9px;width:100%}.action-card small{color:#73899b}.notice{display:flex;justify-content:space-between;gap:12px;border:1px solid #35505e;background:#142633;padding:12px 15px;border-radius:6px;margin-bottom:26px;color:#a9d8e7}.notice.error{border-color:#704448;background:#312125;color:#f3b8b8}.workflow,.work-area,.outputs{border:1px solid #273644;background:#111a24;border-radius:8px;margin-bottom:24px}.workflow{padding:22px}.section-heading{display:flex;align-items:center;justify-content:space-between;margin-bottom:17px}.section-heading h2{margin-bottom:0}.section-heading>span{font-size:11px;color:#8296a8}.steps{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.steps div{background:#0d151d;border:1px solid #24333f;padding:16px;border-radius:6px}.steps b{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#1b3d4c;color:#83ddf0;margin-bottom:14px}.steps strong{display:block;margin-bottom:4px}.steps span{color:#8397a8;font-size:12px}.work-area,.outputs{padding:22px}.quiet{padding:7px 10px!important;font-size:11px!important}.empty{padding:38px;text-align:center;border:1px dashed #334554;border-radius:6px;color:#8296a8;display:grid;gap:8px}.empty strong{color:#bed0df}.items{display:grid;gap:8px}.item{width:100%;display:flex;align-items:center;justify-content:space-between;text-align:left;background:#0e171f!important;padding:13px 15px!important}.item.selected{border-color:#67cde3!important;background:#132631!important}.item div strong{display:block;font-size:13px}.item div span{font-size:11px;color:#7f94a6}.pill{font:10px monospace;background:#1a3040;color:#9bd7e5;padding:5px 8px;border-radius:10px}.next-action{margin-top:16px;padding:18px;background:#16232e;border:1px solid #304555;border-radius:7px;display:flex;align-items:center;justify-content:space-between;gap:20px}.next-action h3,.storyboard h3{margin:3px 0 4px;font-size:16px}.next-action p,.storyboard p,.output-card p{margin:0;color:#879cad;font-size:12px}.working{font-size:11px;color:#e0b36e}.storyboard{margin-top:16px;padding:18px;border:1px solid #345164;border-radius:7px}.storyboard>button:not(.render){width:100%;display:flex;align-items:center;gap:12px;text-align:left;margin-top:8px;background:#0f1922}.storyboard>button.chosen{border-color:#6bd8ee;color:#c8f3fb}.storyboard>button>span{display:grid;place-items:center;width:25px;height:25px;background:#1b3341;border-radius:4px;font:11px monospace}.storyboard>button div strong{display:block;text-transform:capitalize}.storyboard>button div small{color:#8195a6}.storyboard .render{width:100%;margin-top:14px}.output-card{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:16px;border-top:1px solid #263644}.output-card:first-of-type{border-top:0}.output-card>div:first-child>strong{display:block}.output-card>div:first-child>span{font-size:11px;color:#79b9cf}.output-actions{display:flex;gap:8px;align-items:center;flex-shrink:0}.done{color:#73d0a7;font-size:12px}@media(max-width:800px){.simple-header{padding:0 16px}.simulation{display:none}.simple-app main{padding:28px 16px}.hero,.start-grid{grid-template-columns:1fr}.steps{grid-template-columns:1fr 1fr}.health{max-width:500px}.next-action,.output-card{align-items:flex-start;flex-direction:column}.header-actions .connection{display:none}}@media(max-width:520px){.steps{grid-template-columns:1fr}.header-actions button{font-size:11px;padding:7px}.brand small{display:none}}
.settings-backdrop{position:fixed;inset:0;background:#050a10cc;z-index:50;display:flex;justify-content:flex-end}.settings-panel{width:min(640px,100%);height:100%;overflow:auto;background:#111a24;border-left:1px solid #334555;padding:28px}.settings-heading{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;border-bottom:1px solid #293947;padding-bottom:18px;margin-bottom:18px}.settings-heading h2{margin:3px 0 4px;font-size:24px}.settings-heading p{margin:0;color:#879bad}.setting-section{padding:18px 0;border-bottom:1px solid #263644}.setting-section h3{margin:0 0 13px;font-size:14px}.setting-section>label,.triple label{display:grid;gap:7px;color:#a9bac8;font-size:12px}.setting-section>label strong{color:#d8e7f2;font-weight:600}.setting-section input{width:100%;box-sizing:border-box;background:#0c151d;border:1px solid #344957;color:#dce6ef;border-radius:5px;padding:8px}.setting-section input[type=range]{padding:0}.setting-section>p,.technical p{color:#7e93a4;font-size:11px}.triple{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.switch-row{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:10px 0}.switch-row span strong,.switch-row span small{display:block}.switch-row span small{color:#7d92a3}.technical{margin-top:18px;border:1px solid #2b3d4b;border-radius:6px;padding:13px}.technical summary{cursor:pointer;color:#b8c9d6;font-weight:600}.tech-grid{margin-top:14px}.settings-footer{display:flex;justify-content:flex-end;gap:8px;padding-top:22px}@media(max-width:700px){.triple{grid-template-columns:1fr}.settings-panel{padding:20px}}
</style>
