from pydantic import BaseModel,Field,ConfigDict
from typing import Literal
class ProgressTaskInput(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 task_id:str
 status:Literal['not_started','in_progress','completed']
 actual_start:float|None=Field(default=None,ge=0,le=1000000)
 actual_finish:float|None=Field(default=None,ge=0,le=1000000)
class CheckpointInput(BaseModel):
 model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
 scenario_id:str
 observation_time:float=Field(ge=0,le=1000000)
 progress:list[ProgressTaskInput]=Field(min_length=1,max_length=60)
 note:str=Field(min_length=10,max_length=2000)
 correction_of:str|None=None
