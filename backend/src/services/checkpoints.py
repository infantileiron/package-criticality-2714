import uuid,redis
from fastapi import HTTPException
from sqlalchemy import select,func
from src.models import DurationScenario,ProgressCheckpoint
from src.services import queue
from src.services.progress import normalize
from src.utils.serialization import serialize
from src.utils.time import now

def _scenario(db,scenario_id):
 scenario=db.scalar(select(DurationScenario).where(DurationScenario.id==scenario_id).with_for_update())
 if not scenario:raise HTTPException(404,'冻结情景不存在')
 return scenario

def create(db,payload,user):
 scenario=_scenario(db,payload.scenario_id)
 try:state=normalize(scenario.snapshot['package']['tasks'],[[e['predecessor'],e['successor']] for e in scenario.snapshot['dependencies']],payload.observation_time,[r.model_dump() for r in payload.progress])
 except ValueError as e:raise HTTPException(422,str(e))
 correction=None
 if payload.correction_of:
  correction=db.scalar(select(ProgressCheckpoint).where(ProgressCheckpoint.id==payload.correction_of).with_for_update())
  if not correction:raise HTTPException(404,'待更正检查点不存在')
  if correction.scenario_id!=scenario.id:raise HTTPException(422,'待更正检查点须属于同一冻结情景')
  if correction.status!='completed':raise HTTPException(409,'待更正检查点尚未完成推演')
  if correction.correction_of:raise HTTPException(409,'请更正原始检查点，不要在更正记录上继续叠加')
  if abs(correction.observation_time-payload.observation_time)>1e-8:raise HTTPException(422,'迟到更正要保持原观测时点；不同时点请新建常规检查点')
 sequence=(db.scalar(select(func.max(ProgressCheckpoint.sequence)).where(ProgressCheckpoint.scenario_id==scenario.id)) or 0)+1
 item=ProgressCheckpoint(id=str(uuid.uuid4()),scenario_id=scenario.id,sequence=sequence,observation_time=payload.observation_time,progress=state,snapshot=scenario.snapshot,status='queued',result={},error='',correction_of=payload.correction_of,note=payload.note,author=user['email'],created_at=now())
 db.add(item);db.commit()
 try:queue.enqueue(queue.CHECKPOINTS,item.id)
 except redis.RedisError:
  item.status='failed';item.error='后台队列不可用，请重试';db.commit();raise HTTPException(503,item.error)
 return serialize(item)

def listing(db,scenario_id=None):
 query=select(ProgressCheckpoint).order_by(ProgressCheckpoint.created_at.desc())
 if scenario_id:query=query.where(ProgressCheckpoint.scenario_id==scenario_id)
 return [serialize(row) for row in db.scalars(query)]

def detail(db,id):
 item=db.get(ProgressCheckpoint,id)
 if not item:raise HTTPException(404,'进度检查点不存在')
 return serialize(item)
