"""Progress checkpoint engine: actuals for finished tasks, elapsed-based remaining, dependency refusals."""
import sys,os,json
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.services.progress import normalize,baseline_progress,simulate_progress,analyze,cpm_with_release

TASKS=[{'task_id':'T01','name':'A','a':2,'m':2,'b':2},{'task_id':'T02','name':'B','a':2,'m':3,'b':5},{'task_id':'T03','name':'C','a':3,'m':5,'b':7},{'task_id':'T04','name':'D','a':1,'m':1,'b':1}]
EDGES=[['T01','T02'],['T02','T03'],['T03','T04']]
SNAPSHOT={'package':{'tasks':TASKS},'dependencies':[{'predecessor':a,'successor':b} for a,b in EDGES]}

def state(records,observation=4):
 return normalize(TASKS,EDGES,observation,records)

def test_finished_uses_actual_interval():
 result=baseline_progress(TASKS,EDGES,{r['task_id']:r for r in state([{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5}])},4)
 row=next(r for r in result['tasks'] if r['task_id']=='T01')
 assert row['es']==0 and abs(row['ef']-1.5)<1e-9 and abs(row['duration']-1.5)<1e-9

def test_in_progress_remaining_uses_elapsed():
 records=[{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5},{'task_id':'T02','status':'in_progress','actual_start':1.5,'actual_finish':None}]
 result=baseline_progress(TASKS,EDGES,{r['task_id']:r for r in state(records)},4)
 row=next(r for r in result['tasks'] if r['task_id']=='T02')
 assert row['es']==1.5 and abs(row['duration']-3)<1e-9 and abs(row['ef']-4.5)<1e-9
 # remaining m-elapsed = 3-2.5=0.5 is represented by total 3 from start, not 2.5+3
 assert abs(row['duration']-(4-1.5)-0.5)<1e-9

def test_not_started_waits_for_predecessor():
 records=[{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5},{'task_id':'T02','status':'in_progress','actual_start':1.5,'actual_finish':None}]
 result=baseline_progress(TASKS,EDGES,{r['task_id']:r for r in state(records)},4)
 row=next(r for r in result['tasks'] if r['task_id']=='T03')
 assert row['es']==4.5 and row['release']==4

def test_time_contradictions_refused():
 for records,observation in [
  ([{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':3}],2),
  ([{'task_id':'T01','status':'completed','actual_start':2,'actual_finish':1}],4),
  ([{'task_id':'T02','status':'in_progress','actual_start':1,'actual_finish':None}],4),
  ([{'task_id':'T01','status':'not_started','actual_start':1,'actual_finish':None}],4),
  ([{'task_id':'T01','status':'in_progress','actual_start':-1,'actual_finish':None}],4),
  ([{'task_id':'T01','status':'in_progress','actual_start':0,'actual_finish':None}],5),
 ]:
  try:state(records,observation);assert False,'expected rejection'
  except ValueError:pass

def test_dependency_violation_refused():
 for records in [
  [{'task_id':'T02','status':'in_progress','actual_start':1,'actual_finish':None}],
  [{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':2},{'task_id':'T02','status':'in_progress','actual_start':1.5,'actual_finish':None}],
  [{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':2},{'task_id':'T02','status':'completed','actual_start':1.5,'actual_finish':3}],
 ]:
  try:state(records,4);assert False,'expected rejection'
  except ValueError:pass

def test_unknown_and_duplicate_refused():
 for records in ([{'task_id':'ZZ','status':'completed','actual_start':0,'actual_finish':1}],[{'task_id':'T01','status':'not_started','actual_start':None,'actual_finish':None},{'task_id':'T01','status':'not_started','actual_start':None,'actual_finish':None}]):
  try:state(records,4);assert False,'expected rejection'
  except ValueError:pass

def test_checksum_and_samples_reproducible():
 records=[{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5},{'task_id':'T02','status':'in_progress','actual_start':1.5,'actual_finish':None}]
 a=analyze(SNAPSHOT,records,4,200,2410,10);b=analyze(SNAPSHOT,records,4,200,2410,10)
 assert a['checksum']==b['checksum'] and a['risk']['finish_times']==b['risk']['finish_times']
 c=analyze(SNAPSHOT,records,4.5,200,2410,10)
 assert a['checksum']!=c['checksum']

def test_completed_tasks_not_resampled():
 records=[{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5}]
 risk=simulate_progress(TASKS,EDGES,{r['task_id']:r for r in state(records)},4,50,7,10)
 entry=next(r for r in risk['ranges'] if r['task_id']=='T01')
 assert entry['sampled'] is False
 # finish can never be earlier than the completed actual 1.5
 assert min(risk['finish_times'])>=1.5

def test_deadline_before_observation_reports_zero():
 records=[{'task_id':'T01','status':'completed','actual_start':0,'actual_finish':1.5}]
 risk=simulate_progress(TASKS,EDGES,{r['task_id']:r for r in state(records)},4,20,7,2)
 assert risk['on_time_count']==0 and risk['deadline_passed_at_observation'] is True

def test_cpm_release_and_lf_actual_finish():
 run=cpm_with_release({'A':2,'B':3,'C':1},[['A','B'],['B','C']],{'A':0,'B':4,'C':4})
 assert run['tasks'][0]['es']==0 and run['tasks'][0]['ef']==2
 assert next(r for r in run['tasks'] if r['task_id']=='B')['es']==4
 assert next(r for r in run['tasks'] if r['task_id']=='C')['es']==7
 assert run['project_finish']==8

if __name__=='__main__':
 for name,fn in sorted(globals().items()):
  if name.startswith('test_'):
   fn();print('PASS',name)
 print('all progress tests passed')
