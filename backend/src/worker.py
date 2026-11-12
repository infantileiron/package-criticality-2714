from pathlib import Path
import redis,traceback
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.config.database import Session
from src.models import ScheduleRun,DurationScenario,ProgressCheckpoint
from src.services.analysis import analyze
from src.services.progress import analyze as analyze_progress
from src.services import queue
client=redis.Redis.from_url(REDIS_URL);heartbeat=Path('/artifacts/worker-heartbeat')
def execute_run(id):
 with Session() as db:
  run=db.get(ScheduleRun,id)
  if not run or run.status not in ('queued','running'):return
  run.status='running';db.commit()
  try:
   scenario=db.get(DurationScenario,run.scenario_id);run.result=analyze(scenario.snapshot,scenario);run.status='completed'
  except Exception as e:run.error=str(e);run.status='failed';traceback.print_exc()
  db.commit()
def execute_checkpoint(id):
 with Session() as db:
  checkpoint=db.get(ProgressCheckpoint,id)
  if not checkpoint or checkpoint.status not in ('queued','running'):return
  checkpoint.status='running';db.commit()
  try:
   scenario=db.get(DurationScenario,checkpoint.scenario_id)
   checkpoint.result=analyze_progress(checkpoint.snapshot,checkpoint.progress,checkpoint.observation_time,scenario.samples,scenario.seed,scenario.deadline)
   checkpoint.status='completed'
  except Exception as e:checkpoint.error=str(e);checkpoint.status='failed';traceback.print_exc()
  db.commit()
def recover():
 with Session() as db:
  for id in db.scalars(select(ScheduleRun.id).where(ScheduleRun.status.in_(['queued','running']))):client.lpush(queue.RUNS,id)
  for id in db.scalars(select(ProgressCheckpoint.id).where(ProgressCheckpoint.status.in_(['queued','running']))):client.lpush(queue.CHECKPOINTS,id)
def loop():
 while True:
  heartbeat.touch()
  job=client.brpop([queue.RUNS,queue.CHECKPOINTS],timeout=1)
  if not job:continue
  key,payload=job[0].decode(),job[1].decode()
  if key==queue.RUNS:execute_run(payload)
  else:execute_checkpoint(payload)
if __name__=='__main__':
 recover();loop()
