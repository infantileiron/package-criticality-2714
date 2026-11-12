"""Observation-time progress: actual intervals for finished work, elapsed-based remaining time, waiting for predecessors."""
import hashlib,json,math,random,statistics
import heapq
from src.services.cpm import TOLERANCE
from src.services.pert import quantile

STATUSES=('not_started','in_progress','completed')
MAX_CONDITIONAL_DRAWS=64

def _is_number(value):
 return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def normalize(tasks,edges,observation_time,records):
 """Validate progress against the frozen scenario and return a complete per-task state."""
 if not _is_number(observation_time) or observation_time<0:raise ValueError('观测时点须为自项目开工计的非负有限小时数')
 if not isinstance(records,list) or not records:raise ValueError('至少一条进度记录')
 ids={t['task_id'] for t in tasks};state={};ranges={t['task_id']:t for t in tasks}
 for record in records:
  tid=record.get('task_id');status=record.get('status')
  if tid not in ids:raise ValueError(f'进度记录包含情景外任务 {tid}')
  if tid in state:raise ValueError(f'任务 {tid} 存在重复进度记录')
  if status not in STATUSES:raise ValueError(f'任务 {tid} 状态无效')
  start,finish=record.get('actual_start'),record.get('actual_finish')
  for label,value in (('实际开始',start),('实际完成',finish)):
   if value is not None and (not _is_number(value) or value<0):raise ValueError(f'任务 {tid} {label}须为非负有限小时数')
  if status=='not_started':
   if start is not None or finish is not None:raise ValueError(f'未开工任务 {tid} 不得填写实际起止')
  elif status=='in_progress':
   if start is None:raise ValueError(f'在途任务 {tid} 须填写实际开始')
   if finish is not None:raise ValueError(f'在途任务 {tid} 不得填写实际完成')
   if start>observation_time+TOLERANCE:raise ValueError(f'任务 {tid} 实际开始晚于观测时点，时间矛盾')
   if observation_time-start>ranges[tid]['b']+TOLERANCE:raise ValueError(f'在途任务 {tid} 已耗时 {observation_time-start:g}h 超过悲观工期 {ranges[tid]["b"]:g}h；请核对记录或改记实际完成')
  else:
   if start is None or finish is None:raise ValueError(f'已完任务 {tid} 须同时填写实际开始与实际完成')
   if finish<start-TOLERANCE:raise ValueError(f'任务 {tid} 实际完成早于实际开始，时间矛盾')
   if start>observation_time+TOLERANCE:raise ValueError(f'任务 {tid} 实际开始晚于观测时点，时间矛盾')
   if finish>observation_time+TOLERANCE:raise ValueError(f'已完任务 {tid} 实际完成晚于观测时点，时间矛盾')
  state[tid]={'task_id':tid,'status':status,'actual_start':start,'actual_finish':finish}
 # 未列出的任务按观测时点尚未开工，显式补齐便于复核与复现。
 for tid in ids:
  state.setdefault(tid,{'task_id':tid,'status':'not_started','actual_start':None,'actual_finish':None})
 for a,b in edges:
  pred,succ=state[a],state[b]
  if succ['status']=='not_started':continue
  if pred['status']!='completed' or pred['actual_finish'] is None:raise ValueError(f'任务 {b} 已开工，但前置 {a} 尚未完成，违反FS依赖')
  if pred['actual_finish']>succ['actual_start']+TOLERANCE:raise ValueError(f'任务 {b} 实际开始早于前置 {a} 实际完成，违反FS依赖')
 return [state[t['task_id']] for t in sorted(tasks,key=lambda t:t['task_id'])]

def cpm_with_release(durations,edges,releases,tolerance=TOLERANCE):
 """CPM with a per-task release time; ES=max(predecessor EF, release). Unreleased work starts at observation."""
 if not durations:raise ValueError('at least one task required')
 if not math.isfinite(tolerance) or tolerance<0:raise ValueError('invalid tolerance')
 ids=sorted(durations);pred={k:[] for k in ids};succ={k:[] for k in ids};seen=set()
 for edge in edges:
  if len(edge)!=2:raise ValueError('dependency requires predecessor and successor')
  a,b=edge
  if a not in durations or b not in durations:raise ValueError('unknown dependency endpoint')
  if a==b or (a,b) in seen:raise ValueError('self-loop or duplicate dependency')
  seen.add((a,b));succ[a].append(b);pred[b].append(a)
 for k in ids:
  release=releases.get(k)
  if not _is_number(durations[k]) or durations[k]<0:raise ValueError('task durations must be finite nonnegative hours')
  if not _is_number(release) or release<0:raise ValueError('task release times must be finite nonnegative hours')
  degree={k:len(pred[k]) for k in ids};heap=[k for k in ids if not degree[k]];heapq.heapify(heap);order=[]
 while heap:
  k=heapq.heappop(heap);order.append(k)
  for j in sorted(succ[k]):
   degree[j]-=1
   if degree[j]==0:heapq.heappush(heap,j)
 if len(order)!=len(ids):raise ValueError('dependency graph contains a cycle')
 es={};ef={}
 for k in order:
  es[k]=max([releases[k]]+[ef[j] for j in pred[k]]);ef[k]=es[k]+durations[k]
 finish=max(ef.values());ls={};lf={}
 if not math.isfinite(finish):raise ValueError('project finish overflow')
 for k in reversed(order):
  lf[k]=min([ls[j] for j in succ[k]] or [finish]);ls[k]=lf[k]-durations[k]
 rows=[]
 for k in ids:
  slack=ls[k]-es[k]
  if abs(slack)<=tolerance:slack=0.0
  rows.append({'task_id':k,'duration':durations[k],'release':releases[k],'es':es[k],'ef':ef[k],'ls':ls[k],'lf':lf[k],'total_float':slack,'critical':slack<=tolerance,'predecessors':sorted(pred[k]),'successors':sorted(succ[k])})
 critical={r['task_id'] for r in rows if r['critical']};critical_edges=[list(e) for e in sorted(seen) if e[0] in critical and e[1] in critical and abs(ef[e[0]]-es[e[1]])<=tolerance]
 return {'project_finish':finish,'tasks':rows,'topological_order':order,'critical_tasks':sorted(critical),'critical_edges':critical_edges,'tolerance_hours':tolerance,'virtual_source_tasks':[k for k in ids if not pred[k]],'virtual_sink_tasks':[k for k in ids if not succ[k]],'lf_basis':'actual project finish; external deadline never used'}

def _elapsed(record,observation_time):
 return max(0.0,observation_time-(record['actual_start'] or 0.0))

def _network(tasks,edges,state,observation_time,totals):
 durations={};releases={};states={}
 for t in tasks:
  tid=t['task_id'];record=state[tid];status=record['status'];total=totals[tid]
  if status=='completed':durations[tid]=max(0.0,record['actual_finish']-record['actual_start']);releases[tid]=record['actual_start']
  elif status=='in_progress':
   elapsed=_elapsed(record,observation_time);durations[tid]=elapsed if total is None else max(elapsed,float(total));releases[tid]=record['actual_start']
  else:durations[tid]=max(0.0,total);releases[tid]=observation_time
  states[tid]=status
 return durations,releases,states

def baseline_progress(tasks,edges,state,observation_time):
 totals={t['task_id']:t['m'] for t in tasks}
 durations,releases,states=_network(tasks,edges,state,observation_time,totals)
 run=cpm_with_release(durations,edges,releases)
 for row in run['tasks']:
  row['progress_status']=states[row['task_id']]
  rec=state[row['task_id']];row['actual_start']=rec['actual_start'];row['actual_finish']=rec['actual_finish']
 run['observation_time']=observation_time;run['baseline_duration_basis']='completed actual interval; in-progress max(m,elapsed); not-started m'
 return run

def simulate_progress(tasks,edges,state,observation_time,samples,seed,deadline):
 if not tasks or len({t['task_id'] for t in tasks})!=len(tasks):raise ValueError('unique tasks required')
 if isinstance(samples,bool) or not isinstance(samples,int) or not 1<=samples<=10000:raise ValueError('invalid simulation sample count')
 if isinstance(seed,bool) or not isinstance(seed,int) or seed<0:raise ValueError('invalid seed')
 if not _is_number(deadline) or deadline<0:raise ValueError('invalid deadline')
 tasks=sorted(tasks,key=lambda t:t['task_id']);ranges=[]
 for t in tasks:
  a,m,b=t['a'],t['m'],t['b']
  if not all(_is_number(v) for v in (a,m,b)) or not 0<=a<=m<=b:raise ValueError('requires finite 0 <= a <= m <= b')
  alpha=None if a==b else 1+4*(m-a)/(b-a);beta=None if a==b else 1+4*(b-m)/(b-a)
  ranges.append({**t,'alpha':alpha,'beta':beta,'point_mass':a==b})
 rng=random.Random(seed)
 def draw(r):
  a,b=r['a'],r['b']
  return a if r['point_mass'] else a+(b-a)*rng.betavariate(r['alpha'],r['beta'])
 def draw_after(r,elapsed):
  if r['point_mass'] or elapsed>=r['b']-TOLERANCE:return None
  for _ in range(MAX_CONDITIONAL_DRAWS):
   total=draw(r)
   if total>=elapsed-TOLERANCE:return total
  return None
 finish=[];counts={t['task_id']:0 for t in tasks};fallbacks=0
 for _ in range(samples):
  totals={}
  for r in ranges:
   tid=r['task_id'];record=state[tid]
   if record['status']=='completed':totals[tid]=None
   elif record['status']=='in_progress':
    elapsed=_elapsed(record,observation_time);totals[tid]=draw_after(r,elapsed)
    if totals[tid] is None:fallbacks+=1
   else:totals[tid]=draw(r)
  durations={};releases={}
  for t in tasks:
   tid=t['task_id'];record=state[tid];status=record['status']
   if status=='completed':durations[tid]=max(0.0,record['actual_finish']-record['actual_start']);releases[tid]=record['actual_start']
   elif status=='in_progress':
    elapsed=_elapsed(record,observation_time);durations[tid]=elapsed if totals[tid] is None else max(elapsed,float(totals[tid]));releases[tid]=record['actual_start']
   else:durations[tid]=max(0.0,totals[tid]);releases[tid]=observation_time
  run=cpm_with_release(durations,edges,releases,TOLERANCE);finish.append(run['project_finish'])
  for row in run['tasks']:
   if row['critical']:counts[row['task_id']]+=1
 ordered=sorted(finish);on_time=sum(v<=deadline+TOLERANCE for v in finish);low,high=ordered[0],ordered[-1];width=(high-low)/18 if high>low else 0.;hist=[]
 if width:
  bins=[0]*18
  for value in finish:bins[min(17,int((value-low)/width))]+=1
  hist=[{'left':low+i*width,'right':low+(i+1)*width,'count':count} for i,count in enumerate(bins)]
 else:hist=[{'left':low,'right':high,'count':samples}]
 return {'samples':samples,'seed':seed,'deadline':deadline,'observation_time':observation_time,'on_time_count':on_time,'deadline_tolerance_hours':TOLERANCE,'on_time_probability':on_time/samples,'deadline_passed_at_observation':deadline+TOLERANCE<observation_time,'mean_finish':statistics.fmean(finish),'quantiles':{'p05':quantile(ordered,.05),'p50':quantile(ordered,.5),'p80':quantile(ordered,.8),'p95':quantile(ordered,.95)},'finish_times':finish,'histogram':hist,'task_criticality':[{'task_id':t['task_id'],'status':state[t['task_id']]['status'],'critical_count':counts[t['task_id']],'denominator':samples,'criticality':counts[t['task_id']]/samples} for t in tasks],'ranges':[{**r,'sampled':state[r['task_id']]['status']!='completed','conditional_on_elapsed':state[r['task_id']]['status']=='in_progress'} for r in ranges],'conditional_fallback_samples':fallbacks,'lambda':4,'tolerance_hours':TOLERANCE,'quantile_method':'linear interpolation at (n-1)*q','independence_assumption':True}

def summarize(state,observation_time):
 counts={s:sum(1 for r in state if r['status']==s) for s in STATUSES}
 return {'observation_time':observation_time,'completed':counts['completed'],'in_progress':counts['in_progress'],'not_started':counts['not_started'],'total':len(state)}

def analyze(snapshot,state,observation_time,samples,seed,deadline):
 tasks=snapshot['package']['tasks'];edges=[[e['predecessor'],e['successor']] for e in snapshot['dependencies']]
 state=normalize(tasks,edges,observation_time,[{'task_id':r['task_id'],'status':r['status'],'actual_start':r['actual_start'],'actual_finish':r['actual_finish']} for r in state])
 records={r['task_id']:r for r in state}
 baseline=baseline_progress(tasks,edges,records,observation_time);risk=simulate_progress(tasks,edges,records,observation_time,samples,seed,deadline)
 data={'snapshot':snapshot,'progress':state,'observation_time':observation_time,'samples':samples,'seed':seed,'deadline':deadline}
 checksum=hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
 assumptions=['观测时点为自项目开工计的小时数；完工分布与达标率均以该时刻为进度切面，不重置已完成任务的时钟。','已完任务固定使用实际开始与实际完成；未开工任务释放时点取观测时点并等待所有前置实际或推演完成后开工；在途任务已耗时=观测时点-实际开始。','在途任务总工期仅在已耗时之后做Beta-PERT条件抽样（最多64次尝试；若已耗时达到悲观b或尝试耗尽，则按已耗时收口，剩余0小时），剩余=总工期-已耗时。','未抽样任务为已完任务；抽样序列按任务ID排序，固定seed、观测时点与进度记录可复现同一检查点校验和。','每次抽样以释放时点重新计算CPM；关键任务按该次总时差<=1e-8小时判定，不套用基线关键集合。','达标为项目完工<=deadline+1e-8小时；deadline为自项目开工计的绝对小时数，早于观测时点时仍如实给出0达标，不视为进度矛盾。','工期相互独立，未模拟天气共因、共享人员设备、日历与资源竞争；有限样本比例不是交付保证。']

 return {'baseline':baseline,'risk':risk,'tasks':tasks,'edges':edges,'progress':state,'observation_time':observation_time,'samples':samples,'seed':seed,'deadline':deadline,'checksum':checksum,'summary':summarize(state,observation_time),'assumptions':assumptions}
