import json
from sqlalchemy import select,func
from src.config.database import Base,engine,Session
from src.models import User,WorkPackage,TaskDependency,DurationScenario,ScheduleRun,DeliveryReview,Report,ProgressCheckpoint
from src.services.analysis import analyze
from src.services.progress import analyze as analyze_progress
from src.utils.security import hash_password
from src.utils.time import now
from src.utils.serialization import serialize

def seed():
 Base.metadata.create_all(engine)
 with Session() as db:
  for role in ('admin','analyst','viewer'):
   if not db.get(User,role):db.add(User(id=role,email=role+'@duochuan.demo',password=hash_password('Schedule2026!'),role=role))
  names=['现场交接','区域围护','测量复核','工器具核验','基层清理','支座检查','连接件检测','电缆隔离','钻孔定位','锚固施工','边梁加固','排水修补','防护层修复','支架复验','承载复测','密封施工','绝缘复核','灌浆养护','界面验收','防护恢复','联合复检','现场交付','资料封版','独立备件盘点'];modes=[2,3,2,1,4,3,4,2,3,5,4,3,2,3,4,2,3,6,2,2,3,2,1,4]
  tasks=[{'task_id':f'T{i+1:02}','name':name,'a':float(m if i in (0,23) else round(m*.7,2)),'m':float(m),'b':float(m if i in (0,23) else round(m*1.7,2))} for i,(name,m) in enumerate(zip(names,modes))]
  if not db.get(WorkPackage,'demo-package'):db.add(WorkPackage(id='demo-package',name='铎川·检修通道加固工作包',source='duochuan_workpackage_20261112.json',tasks=tasks,created_at=now()));db.flush()
  edges=[(1,5),(1,6),(2,6),(2,7),(3,7),(4,8),(5,9),(6,10),(6,11),(7,11),(7,12),(8,13),(9,14),(10,14),(10,15),(11,15),(12,16),(13,17),(14,18),(15,18),(15,19),(16,19),(17,20),(18,21),(19,21),(19,22),(20,22),(20,23),(5,10),(12,17)]
  for i,(a,b) in enumerate(edges,1):
   if not db.get(TaskDependency,f'demo-edge-{i}'):db.add(TaskDependency(id=f'demo-edge-{i}',package_id='demo-package',predecessor=f'T{a:02}',successor=f'T{b:02}',created_at=now()))
  db.flush()
  if not db.get(DurationScenario,'demo-scenario'):
   snapshot={'package':serialize(db.get(WorkPackage,'demo-package')),'dependencies':[serialize(e) for e in db.scalars(select(TaskDependency).where(TaskDependency.package_id=='demo-package').order_by(TaskDependency.predecessor,TaskDependency.successor))]}
   db.add(DurationScenario(id='demo-scenario',name='通道加固·32小时交付风险基线',package_id='demo-package',version=1,deadline=32.,samples=1500,seed=2410,snapshot=snapshot,created_at=now()))
  db.flush()
  if not db.get(ScheduleRun,'demo-run'):db.add(ScheduleRun(id='demo-run',scenario_id='demo-scenario',status='completed',result=analyze(db.get(DurationScenario,'demo-scenario').snapshot,db.get(DurationScenario,'demo-scenario')),error='',created_at=now()));db.flush()
  if not db.get(DeliveryReview,'demo-review'):db.add(DeliveryReview(id='demo-review',run_id='demo-run',version=1,note='已核对FS依赖与基线时差，模拟每次重算关键度；独立工期未涵盖共享资源、天气共因，32小时达标比例不是交付保证。',decision='accepted',author='analyst@duochuan.demo',created_at=now()));db.flush()
  if not db.get(Report,'demo-report'):db.add(Report(id='demo-report',run_id='demo-run',review_id='demo-review',title='铎川通道加固·基线与风险复核',published_by='admin@duochuan.demo',created_at=now()))
  db.flush()
  if not db.get(ProgressCheckpoint,'demo-checkpoint'):
   completed=[('T01',0.,2.),('T02',0.,3.),('T03',0.,2.),('T04',0.,1.)]
   in_progress=[('T05',2.),('T06',3.),('T07',3.),('T08',4.5)]
   progress=[{'task_id':tid,'status':'completed','actual_start':start,'actual_finish':finish} for tid,start,finish in completed]+[{'task_id':tid,'status':'in_progress','actual_start':start,'actual_finish':None} for tid,start in in_progress]
   progress+= [{'task_id':f'T{i:02}','status':'not_started','actual_start':None,'actual_finish':None} for i in range(9,25)]
   scenario=db.get(DurationScenario,'demo-scenario')
   db.add(ProgressCheckpoint(id='demo-checkpoint',scenario_id='demo-scenario',sequence=1,observation_time=6.,progress=progress,snapshot=scenario.snapshot,status='completed',result=analyze_progress(scenario.snapshot,progress,6.,scenario.samples,scenario.seed,scenario.deadline),error='',correction_of=None,note='09:20现场进度：T01-T04已完成，T05-T08在途，其余等待前置；冻结情景与三点工期不变。',author='analyst@duochuan.demo',created_at=now()))
  db.commit();return {m.__tablename__:db.scalar(select(func.count()).select_from(m)) for m in (User,WorkPackage,TaskDependency,DurationScenario,ScheduleRun,DeliveryReview,Report,ProgressCheckpoint)}
if __name__=='__main__':print(json.dumps(seed(),ensure_ascii=False))
