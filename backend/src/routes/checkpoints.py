from fastapi import APIRouter,Depends
from src.config.database import db_session
from src.controllers.auth import current_user,writer
from src.schemas.checkpoint import CheckpointInput
from src.services import checkpoints as service
router=APIRouter(prefix='/checkpoints')
@router.get('')
def listing(scenario_id:str|None=None,db=Depends(db_session),user=Depends(current_user)):return service.listing(db,scenario_id)
@router.post('')
def create(payload:CheckpointInput,db=Depends(db_session),user=Depends(writer)):return service.create(db,payload,user)
@router.get('/{id}')
def detail(id:str,db=Depends(db_session),user=Depends(current_user)):return service.detail(db,id)
