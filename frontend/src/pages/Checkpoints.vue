<script setup lang="ts">
import {ref,computed,watch} from 'vue';
import type {Workspace} from '../stores/workspace';
import type {Checkpoint,CheckpointResult,ProgressRecord,Scenario} from '../types/domain';
import {create} from '../api/checkpoints';
import {download} from '../api/client';
import {useAction} from '../hooks/useAction';
import {num,pct,short} from '../utils/format';
import {PROGRESS_STATUSES,RUN_STATUSES} from '../constants/enums';
import Heading from '../components/common/Heading.vue';
import Notice from '../components/common/Notice.vue';
import Empty from '../components/common/Empty.vue';
import Status from '../components/common/Status.vue';
import ScenarioStrip from '../components/ScenarioStrip.vue';
import RiskSummary from '../components/RiskSummary.vue';
import Histogram from '../components/Histogram.vue';
import CriticalityBars from '../components/CriticalityBars.vue';
import CpmTable from '../components/CpmTable.vue';
const props=defineProps<{data:Workspace;canWrite:boolean;refresh:()=>Promise<void>}>();
const scenarioId=ref('demo-scenario'),observationTime=ref(8),correctionOf=ref<string|null>(null),note=ref(''),selected=ref(''),tab=ref('summary');
const scenario=computed<Scenario|undefined>(()=>props.data.scenarios.find(s=>s.id===scenarioId.value)||props.data.scenarios[0]);
const checkpoints=computed(()=>props.data.checkpoints.filter(c=>c.scenario_id===scenario.value?.id));
const rows=ref<ProgressRecord[]>([]);
const base=computed<Checkpoint|undefined>(()=>props.data.checkpoints.find(c=>c.id===correctionOf.value));
const current=computed<Checkpoint|undefined>(()=>props.data.checkpoints.find(c=>c.id===selected.value)||checkpoints.value[0]);
function done(c?:Checkpoint):CheckpointResult|null{return c&&c.status==='completed'?c.result as CheckpointResult:null}
const result=computed(()=>done(current.value));
const{busy,error,notice,act}=useAction();
function resetRows(source?:Checkpoint){
 const tasks=scenario.value?.snapshot.package.tasks||[];
 rows.value=tasks.slice().sort((a,b)=>a.task_id.localeCompare(b.task_id)).map(t=>{
  const found=source?.progress.find(p=>p.task_id===t.task_id);
  return {task_id:t.task_id,status:found?.status||'not_started',actual_start:found?.actual_start??null,actual_finish:found?.actual_finish??null};
 });
}
watch(()=>scenario.value?.id,()=>{correctionOf.value=null;note.value='';selected.value='';resetRows()},{immediate:true});
function beginCorrection(c:Checkpoint){correctionOf.value=c.id;observationTime.value=c.observation_time;selected.value=c.id;note.value='';resetRows(c)}
function cancelCorrection(){correctionOf.value=null;note.value='';resetRows()}
function timeValue(value:number|null){return value===null||value===undefined||(value as unknown)===''?null:Number(value)}
function submit(){
 return create({scenario_id:scenario.value!.id,observation_time:Number(observationTime.value),correction_of:correctionOf.value,note:note.value,progress:rows.value.map(r=>({task_id:r.task_id,status:r.status,actual_start:r.status==='not_started'?null:timeValue(r.actual_start),actual_finish:r.status==='completed'?timeValue(r.actual_finish):null}))}).then(c=>{selected.value=c.id;note.value='';correctionOf.value=null;return props.refresh()});
}
const runs=computed(()=>props.data.runs.filter(r=>r.scenario_id===scenario.value?.id));
const reports=computed(()=>props.data.reports.filter(r=>runs.value.some(run=>run.id===r.run_id)));
const correctionBase=computed(()=>base.value?`#${base.value.sequence} / 观测 ${num(base.value.observation_time)}h`:'');
</script>
<template>
<Heading index="07 / PROGRESS CHECKPOINTS" title="已开工，就按此刻重算。" detail="冻结情景不变；按观测时点记录已完实际区间、在途已耗时与未开工等待。迟到更正生成新检查点并重算，旧检查点原样保留。"/>
<label class="selector">冻结情景<select aria-label="冻结情景" v-model="scenarioId"><option v-for="s in data.scenarios" :key="s.id" :value="s.id">{{s.name}} · v{{s.version}}</option></select></label>
<Empty v-if="!scenario">先在风险情景页冻结一份任务与FS依赖快照。</Empty>
<template v-else>
<ScenarioStrip :scenario="scenario"/>
<section v-if="canWrite" class="form-section">
<h2>{{correctionOf?'迟到更正 · 观测时点锁定 '+correctionBase:'录入进度检查点'}}</h2>
<p>未列出的任务按未开工处理；未开工任务以观测时点为释放时点并等待全部前置完成。已完任务固定使用实际起止，在途任务按已耗时推演剩余。</p>
<form @submit.prevent="act(submit,'检查点已提交后台重算')">
<label>观测时点 / 自项目开工计小时<input aria-label="观测时点" type="number" min="0" step="any" v-model.number="observationTime" :disabled="!!correctionOf"/></label>
<div class="table-scroll"><table class="progress-table"><thead><tr><th>任务</th><th>状态</th><th>实际开始 / h</th><th>实际完成 / h</th></tr></thead><tbody><tr v-for="row in rows" :key="row.task_id"><td><b>{{row.task_id}}</b> {{scenario.snapshot.package.tasks.find(t=>t.task_id===row.task_id)?.name}}</td><td><select :aria-label="row.task_id+' 状态'" v-model="row.status"><option v-for="(label,key) in PROGRESS_STATUSES" :key="key" :value="key">{{label}}</option></select></td><td><input :aria-label="row.task_id+' 实际开始'" type="number" min="0" step="any" v-model="row.actual_start" :disabled="row.status==='not_started'"/></td><td><input :aria-label="row.task_id+' 实际完成'" type="number" min="0" step="any" v-model="row.actual_finish" :disabled="row.status!=='completed'"/></td></tr></tbody></table></div>
<label>检查点说明<textarea aria-label="检查点说明" v-model="note" rows="2" required minlength="10" placeholder="例：09:20 现场记录，T01-T04已完成，T05在途。"/></label>
<div class="actions"><button class="primary" :disabled="busy">{{correctionOf?'提交迟到更正并重算':'提交进度检查点'}}</button><button v-if="correctionOf" type="button" @click="cancelCorrection">取消更正</button></div>
</form><Notice :error="error" :notice="notice"/>
</section>
<Empty v-if="!checkpoints.length">录入第一条进度检查点后，这里会显示自项目开工计的完工分布、达标率与关键任务。</Empty>
<template v-else>
<div class="section-rule"><h2>检查点版本 / 同一冻结情景</h2><span>旧版本结果与校验和保持可复现</span></div>
<article v-for="c in checkpoints" :key="c.id" class="scenario-row">
<div><p class="eyebrow">CHECKPOINT #{{c.sequence}} · 观测 {{num(c.observation_time)}}h · {{c.author}}<template v-if="c.correction_of"> · 更正 → #{{checkpoints.find(x=>x.id===c.correction_of)?.sequence}}</template></p><h2>{{c.note}}</h2><p><Status :value="c.status"/><span v-if="done(c)"> · 校验和 {{short(done(c)!.checksum)}} · 已完 {{done(c)!.summary.completed}} / 在途 {{done(c)!.summary.in_progress}} / 未开工 {{done(c)!.summary.not_started}}</span><span v-if="c.status==='failed'"> · {{c.error}}</span></p></div>
<div><button :disabled="busy" @click="selected=c.id;tab='summary'">查看检查点</button><button v-if="canWrite&&c.status==='completed'&&!c.correction_of" :disabled="busy" @click="beginCorrection(c)">登记迟到更正</button></div>
</article>
<template v-if="current">
<div class="result-meta"><Status :value="current.status"/><span>CHECKPOINT #{{current.sequence}}</span><span>OBSERVED {{num(current.observation_time)}}h</span><span v-if="result">SHA256 {{short(result.checksum)}}</span></div>
<p v-if="current.status==='queued'||current.status==='running'" role="status" class="notice">后台正按观测时点重算已完/在途/未开工任务，完成后自动刷新。</p>
<p v-if="current.status==='failed'" role="alert" class="notice error">{{current.error}} · 已保留失败记录，调整进度后重新提交。</p>
<template v-if="result">
<RiskSummary :result="result"/>
<p v-if="result.risk.deadline_passed_at_observation" class="notice">观测时点 {{num(result.observation_time)}}h 已晚于截止期 {{num(result.risk.deadline)}}h：达标率如实为 {{pct(result.risk.on_time_probability)}}，不因迟到记录而改写。</p>
<div class="tabs"><button :class="{active:tab==='summary'}" @click="tab='summary'">完工分布与达标</button><button :class="{active:tab==='critical'}" @click="tab='critical'">关键任务</button><button :class="{active:tab==='cpm'}" @click="tab='cpm'">CPM时刻与进度</button></div>
<section v-if="tab==='summary'" class="evidence-section"><h2>自项目开工计 · 完工样本与达标率</h2><Histogram :risk="result.risk"/><div class="quantiles"><span v-for="(v,k) in result.risk.quantiles" :key="k">{{k}} <b>{{num(v)}}h</b></span><span>均值 <b>{{num(result.risk.mean_finish)}}h</b></span></div><p class="muted">在途任务总工期在已耗时之后条件抽样；样本 {{result.risk.samples}} 次（seed {{result.risk.seed}}），条件收口样本 {{result.risk.conditional_fallback_samples}} 次。达标为完工≤{{num(result.risk.deadline)}}h + {{result.risk.deadline_tolerance_hours}}h 容差；有限样本比例不是交付保证。</p></section>
<section v-else-if="tab==='critical'" class="evidence-section"><h2>每次重算的关键任务</h2><CriticalityBars :risk="result.risk" :tasks="result.tasks"/><p class="muted">关键度为该次抽样总时差≤{{result.risk.tolerance_hours}}h 的次数 / {{result.risk.samples}}；已完任务仍参与后续依赖的CPM。</p></section>
<section v-else class="evidence-section"><div class="section-rule"><h2>进度切面 / 实际与剩余</h2><span>{{result.baseline.baseline_duration_basis}}</span></div><CpmTable :baseline="result.baseline" :tasks="result.tasks"/></section>
<details><summary>进度记录、假设边界与校验和</summary><div class="table-scroll"><table><thead><tr><th>任务</th><th>状态</th><th>实际开始</th><th>实际完成</th><th>基线工期</th><th>释放时点</th></tr></thead><tbody><tr v-for="r in result.progress" :key="r.task_id"><td>{{r.task_id}}</td><td>{{PROGRESS_STATUSES[r.status]}}</td><td>{{r.actual_start===null?'—':num(r.actual_start)}}</td><td>{{r.actual_finish===null?'—':num(r.actual_finish)}}</td><td>{{num(result.baseline.tasks.find(t=>t.task_id===r.task_id)?.duration??0)}}</td><td>{{num(result.baseline.tasks.find(t=>t.task_id===r.task_id)?.release??0)}}</td></tr></tbody></table></div><p v-for="s in result.assumptions" :key="s">{{s}}</p><p class="mono">{{result.checksum}}</p></details>
</template>
</template>
<div class="section-rule"><h2>原情景结果与批准报告</h2><span>只读保留，不因进度检查点改写</span></div>
<p v-if="!runs.length" class="muted">该情景尚无原始推演运行。</p>
<div class="table-scroll" v-if="runs.length"><table><thead><tr><th>运行</th><th>状态</th><th>原完工 P50 / 达标率</th><th>批准报告</th></tr></thead><tbody><tr v-for="r in runs" :key="r.id"><td class="mono">{{short(r.id)}}</td><td>{{RUN_STATUSES[r.status]}}</td><td><template v-if="r.status==='completed'">{{num(r.result.risk.quantiles.p50)}}h / {{pct(r.result.risk.on_time_probability)}}（{{r.result.risk.on_time_count}}/{{r.result.risk.samples}}）</template><template v-else>—</template></td><td><button v-for="rp in reports.filter(x=>x.run_id===r.id)" :key="rp.id" @click="act(()=>download(rp.id),'CSV已下载')">下载批准CSV</button><span v-if="!reports.some(x=>x.run_id===r.id)" class="muted">—</span></td></tr></tbody></table></div>
<p class="footnote"><b>口径</b><span>观测时点自项目开工计；已完任务使用实际起止，在途任务用 max(已耗时, 条件总工期) 推演剩余，未开工任务以观测时点为释放时点等待前置。迟到更正保持原观测时点并生成新版本，旧检查点内容与校验和不变。deadline 始终是外部绝对时点，不参与 CPM 的 LF。</span></p>
</template>
</template>
</template>
