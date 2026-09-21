<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../stores/control'

type AgentState = 'WORKING'|'IDLE'|'STALE'|'OFFLINE'
interface AgentTarget {
  id:string
  object_type:string
  title:string
  status:string
}
interface AgentTask {
  id:string
  type:string
  status:string
  attempt:number
  max_attempts:number
  priority:number
  started_at:string|null
  payload:Record<string,unknown>
}
interface AgentSensors {
  cpu_percent:number|null
  rss_mb:number|null
  process_uptime_seconds:number|null
  threads:number|null
}
interface AgentActivity {
  event_type:string
  timestamp:string
  object_id:string|null
  object_type:string|null
  severity:string|null
}
interface Agent {
  id:string
  label:string
  kind:string
  role:string
  state:AgentState
  hostname:string|null
  pid:number|null
  resource_class:string|null
  queues:string[]
  task:AgentTask|null
  target:AgentTarget|null
  trace_id:string|null
  heartbeat_at:number|null
  heartbeat_age_seconds:number|null
  lease_remaining_seconds:number
  sensors:AgentSensors
  stats:{assigned:number;succeeded:number;retrying:number;dead_letter:number}
  recent_activity:AgentActivity[]
}
interface Telemetry {
  server_time:number
  lease_seconds:number
  summary:{known_agents:number;online:number;working:number;idle:number;stale:number;offline:number}
  agents:Agent[]
}

const emit=defineEmits<{ inspect:[id:string] }>()
const data=ref<Telemetry|null>(null)
const error=ref('')
const expanded=ref<string|null>(null)
let timer:ReturnType<typeof setInterval>|undefined

const agents=computed(()=>data.value?.agents||[])
const summary=computed(()=>data.value?.summary||{known_agents:0,online:0,working:0,idle:0,stale:0,offline:0})

const taskNames:Record<string,string>={
  DISCOVER:'Searching source',
  FETCH_METADATA:'Reading metadata',
  NORMALIZE:'Preparing media',
  DEDUPLICATE:'Checking duplicates',
  ANALYZE_TEXT:'Reading text',
  ANALYZE_VIDEO:'Analyzing video',
  EMBED:'Creating semantic fingerprint',
  TRANSCRIBE:'Transcribing audio',
  ATOMIZE:'Extracting moments',
  CLUSTER:'Grouping trend',
  ROUTE:'Matching destination',
  COMPOSE:'Building composition',
  RENDER:'Rendering clip',
  REVIEW:'Preparing review',
  PUBLISH:'Publishing',
  COLLECT_METRICS:'Collecting performance',
  UPDATE_MODEL:'Updating model',
}

async function refresh(){
  try{
    data.value=await api<Telemetry>('/agents/telemetry')
    error.value=''
  }catch(e){ error.value=String(e) }
}
function stateLabel(state:AgentState){
  return {WORKING:'Working',IDLE:'Standing by',STALE:'Heartbeat lost',OFFLINE:'Offline'}[state]
}
function objective(agent:Agent){
  if(!agent.task) return agent.state==='OFFLINE'?'No live heartbeat':'Awaiting task'
  const name=taskNames[agent.task.type]||agent.task.type.split('_').join(' ').toLowerCase()
  return agent.state==='WORKING'?name:'Last: '+name
}
function age(seconds:number|null){
  if(seconds===null) return '—'
  if(seconds<1) return '<1s'
  if(seconds<60) return Math.floor(seconds)+'s'
  return Math.floor(seconds/60)+'m'
}
function lease(seconds:number){
  if(seconds<=0) return '—'
  if(seconds<10) return seconds.toFixed(1)+'s'
  return Math.round(seconds)+'s'
}
function runtime(started:string|null){
  if(!started) return '—'
  const delta=Math.max(0,Date.now()-new Date(started).getTime())/1000
  if(delta<60) return Math.floor(delta)+'s'
  const m=Math.floor(delta/60)
  return m<60?m+'m':Math.floor(m/60)+'h '+(m%60)+'m'
}
function eventName(value:string){
  return value.split('_').join(' ').toLowerCase()
}
function shortId(value:string|null){
  if(!value) return '—'
  return value.length>14?value.slice(0,7)+'…'+value.slice(-5):value
}

onMounted(async()=>{ await refresh();timer=setInterval(()=>void refresh(),1000) })
onUnmounted(()=>{ if(timer)clearInterval(timer) })
</script>

<template>
  <section class="agent-ops">
    <div class="ops-heading">
      <div>
        <p class="ops-kicker">AGENT OPS · LIVE SENSOR</p>
        <h2>Execution agents</h2>
        <p>Every card is tied to the worker's actual process heartbeat, task lease and current object.</p>
      </div>
      <div class="fleet">
        <div><strong>{{summary.online}}</strong><span>online</span></div>
        <div><strong>{{summary.working}}</strong><span>working</span></div>
        <div><strong>{{summary.idle}}</strong><span>standing by</span></div>
        <div :class="{attention:summary.stale+summary.offline>0}"><strong>{{summary.stale+summary.offline}}</strong><span>attention</span></div>
      </div>
    </div>

    <div v-if="error" class="ops-error">{{error}}</div>
    <div v-if="!agents.length && !error" class="ops-empty">
      <span class="empty-pulse"></span>
      <div><strong>Waiting for agent heartbeats</strong><small>Execution processes appear here as soon as their presence channel comes online.</small></div>
    </div>

    <div v-else class="agent-grid">
      <article v-for="agent in agents" :key="agent.id" class="agent-card" :class="agent.state.toLowerCase()">
        <div class="agent-top">
          <div class="identity">
            <span class="pulse" :class="agent.state.toLowerCase()"></span>
            <div>
              <strong>{{agent.role}}</strong>
              <small>{{agent.label}}<template v-if="agent.pid"> · PID {{agent.pid}}</template></small>
            </div>
          </div>
          <span class="state" :class="agent.state.toLowerCase()">{{stateLabel(agent.state)}}</span>
        </div>

        <div class="objective">
          <span>{{agent.state==='WORKING'?'CURRENT OBJECTIVE':'STATUS'}}</span>
          <strong>{{objective(agent)}}</strong>
          <button v-if="agent.target" type="button" @click="emit('inspect',agent.target.id)">
            {{agent.target.title}}
            <small>{{agent.target.object_type}} · {{agent.target.status}}</small>
          </button>
          <small v-else>{{agent.state==='WORKING'?'Resolving task target…':'No object currently assigned'}}</small>
        </div>

        <div class="sensor-row">
          <div><span>Heartbeat</span><strong>{{age(agent.heartbeat_age_seconds)}} ago</strong></div>
          <div><span>CPU</span><strong>{{agent.sensors.cpu_percent===null?'—':agent.sensors.cpu_percent.toFixed(1)+'%'}}</strong></div>
          <div><span>Memory</span><strong>{{agent.sensors.rss_mb===null?'—':agent.sensors.rss_mb.toFixed(1)+' MB'}}</strong></div>
          <div><span>Task runtime</span><strong>{{runtime(agent.task?.started_at||null)}}</strong></div>
          <div><span>Lease</span><strong>{{lease(agent.lease_remaining_seconds)}}</strong></div>
          <div><span>Attempt</span><strong>{{agent.task?agent.task.attempt+'/'+agent.task.max_attempts:'—'}}</strong></div>
        </div>

        <button class="details-toggle" type="button" @click="expanded=expanded===agent.id?null:agent.id">
          {{expanded===agent.id?'Hide sensor detail':'Sensor detail'}}
          <span>{{expanded===agent.id?'−':'+'}}</span>
        </button>

        <div v-if="expanded===agent.id" class="sensor-detail">
          <div class="detail-grid">
            <div><span>Agent ID</span><strong :title="agent.id">{{shortId(agent.id)}}</strong></div>
            <div><span>Host</span><strong>{{agent.hostname||'—'}}</strong></div>
            <div><span>Process uptime</span><strong>{{agent.sensors.process_uptime_seconds===null?'—':age(agent.sensors.process_uptime_seconds)}}</strong></div>
            <div><span>Threads</span><strong>{{agent.sensors.threads??'—'}}</strong></div>
            <div><span>Queues</span><strong>{{agent.queues.join(', ')||'—'}}</strong></div>
            <div><span>Task ID</span><strong :title="agent.task?.id||''">{{shortId(agent.task?.id||null)}}</strong></div>
            <div><span>Trace</span><strong :title="agent.trace_id||''">{{shortId(agent.trace_id)}}</strong></div>
            <div><span>Completed</span><strong>{{agent.stats.succeeded}} / {{agent.stats.assigned}}</strong></div>
            <div><span>Retrying</span><strong>{{agent.stats.retrying}}</strong></div>
            <div><span>Dead letter</span><strong>{{agent.stats.dead_letter}}</strong></div>
          </div>

          <div class="activity">
            <span>RECENT TRACE</span>
            <div v-if="!agent.recent_activity.length" class="no-activity">No task events yet.</div>
            <div v-for="event in agent.recent_activity" :key="event.timestamp+event.event_type" class="activity-row">
              <i></i>
              <div><strong>{{eventName(event.event_type)}}</strong><small>{{new Date(event.timestamp).toLocaleTimeString()}}</small></div>
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.agent-ops{border:1px solid #2a3d4c;background:#101a23;border-radius:9px;padding:22px;margin-bottom:24px}.ops-heading{display:flex;align-items:flex-end;justify-content:space-between;gap:22px;margin-bottom:18px}.ops-kicker{margin:0 0 5px;color:#77a4b8;font:10px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:1.35px}.ops-heading h2{margin:0 0 4px;font-size:20px;font-weight:560}.ops-heading p:not(.ops-kicker){margin:0;color:#8196a7;font-size:12px}.fleet{display:grid;grid-template-columns:repeat(4,minmax(70px,1fr));border:1px solid #293d4b;border-radius:6px;overflow:hidden;flex-shrink:0}.fleet div{padding:9px 12px;border-right:1px solid #293d4b;background:#0c151d}.fleet div:last-child{border-right:0}.fleet strong,.fleet span{display:block}.fleet strong{font-size:16px}.fleet span{font-size:9px;color:#72899b;text-transform:uppercase;letter-spacing:.65px}.fleet .attention strong{color:#e2aa72}.agent-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.agent-card{min-width:0;border:1px solid #293b48;background:#0c151d;border-radius:7px;padding:15px}.agent-card.working{border-color:#386477}.agent-card.stale{border-color:#845c43}.agent-card.offline{opacity:.72}.agent-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}.identity{display:flex;align-items:center;gap:10px;min-width:0}.identity strong,.identity small{display:block}.identity strong{font-size:13px}.identity small{font-size:10px;color:#748a9b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.pulse{position:relative;width:10px;height:10px;border-radius:50%;background:#6f8490;flex:0 0 auto}.pulse.working,.pulse.idle{background:#72c8ae}.pulse.working:after{content:"";position:absolute;inset:-5px;border:1px solid #72c8ae;border-radius:50%;animation:pulse 1.2s ease-out infinite}.pulse.stale{background:#d49761}.pulse.offline{background:#6a7379}.state{font:9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.6px;text-transform:uppercase;border:1px solid #334753;border-radius:999px;padding:4px 7px;color:#8ba2b2;white-space:nowrap}.state.working{color:#88d8c0;border-color:#356655}.state.stale{color:#e0aa79;border-color:#694c38}.objective{margin-top:14px;padding:12px;background:#101e28;border:1px solid #223744;border-radius:5px}.objective>span{display:block;font:9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.9px;color:#6f899b}.objective>strong{display:block;margin:3px 0 6px;font-size:13px;font-weight:600}.objective>small{color:#718798;font-size:10px}.objective button{width:100%;text-align:left;background:transparent;border:0;padding:0;color:#b9d1df;cursor:pointer;font-size:11px}.objective button small{display:block;color:#718798;font-size:9px;margin-top:2px}.sensor-row{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;margin-top:11px;background:#263844;border:1px solid #263844;border-radius:5px;overflow:hidden}.sensor-row div{background:#0b141c;padding:8px;min-width:0}.sensor-row span,.sensor-row strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sensor-row span{font-size:8px;color:#667f91;text-transform:uppercase;letter-spacing:.5px}.sensor-row strong{font:10px ui-monospace,SFMono-Regular,Menlo,monospace;color:#a9bdca;margin-top:2px}.details-toggle{display:flex;justify-content:space-between;width:100%;margin-top:10px;padding:7px 0;border:0;border-top:1px solid #22323d;background:transparent;color:#7790a1;font-size:10px;cursor:pointer}.sensor-detail{padding-top:4px}.detail-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.detail-grid div{background:#0a1219;padding:7px;border-radius:4px;min-width:0}.detail-grid span,.detail-grid strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.detail-grid span{font-size:8px;color:#637a8a;text-transform:uppercase}.detail-grid strong{font:9px ui-monospace,SFMono-Regular,Menlo,monospace;color:#9eb3bf;margin-top:2px}.activity{margin-top:12px}.activity>span{font:9px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.8px;color:#6d8798}.activity-row{display:flex;gap:8px;align-items:center;border-top:1px solid #1e2d37;padding:6px 0}.activity-row i{width:5px;height:5px;background:#62889a;border-radius:50%;flex:0 0 auto}.activity-row div{min-width:0}.activity-row strong{display:block;font-size:9px;font-weight:500;color:#9fb2bf;text-transform:capitalize}.activity-row small{display:block;font-size:8px;color:#657a88}.no-activity{font-size:9px;color:#607685;padding:8px 0}.ops-error{border:1px solid #67464a;color:#d8a3a8;padding:10px;border-radius:5px}.ops-empty{display:flex;align-items:center;gap:12px;padding:18px;border:1px dashed #2f4554;border-radius:6px;color:#7b92a2}.ops-empty strong,.ops-empty small{display:block}.ops-empty strong{color:#aabeca}.ops-empty small{font-size:10px}.empty-pulse{width:9px;height:9px;border-radius:50%;background:#637b89;animation:pulse 1.5s ease-out infinite}@keyframes pulse{0%{transform:scale(.8);opacity:1}100%{transform:scale(2.2);opacity:0}}@media(prefers-reduced-motion:reduce){.pulse.working:after,.empty-pulse{animation:none}}@media(max-width:850px){.ops-heading{align-items:stretch;flex-direction:column}.fleet{width:100%}.agent-grid{grid-template-columns:1fr}}@media(max-width:700px){.sensor-row{grid-template-columns:repeat(3,1fr)}}@media(max-width:520px){.fleet{grid-template-columns:repeat(2,1fr)}.fleet div:nth-child(2){border-right:0}.fleet div:nth-child(-n+2){border-bottom:1px solid #293d4b}.sensor-row,.detail-grid{grid-template-columns:repeat(2,1fr)}}
</style>
