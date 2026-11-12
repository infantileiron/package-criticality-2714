from sqlalchemy import String,Double,Integer,JSON,ForeignKey,Text,UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class ProgressCheckpoint(Base):
 __tablename__='progress_checkpoints'
 __table_args__=(UniqueConstraint('scenario_id','sequence'),)
 id:Mapped[str]=mapped_column(String(80),primary_key=True)
 scenario_id:Mapped[str]=mapped_column(ForeignKey('duration_scenarios.id'))
 sequence:Mapped[int]=mapped_column(Integer)
 observation_time:Mapped[float]=mapped_column(Double)
 progress:Mapped[list]=mapped_column(JSON,default=list)
 snapshot:Mapped[dict]=mapped_column(JSON,default=dict)
 status:Mapped[str]=mapped_column(String(32))
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 error:Mapped[str]=mapped_column(Text,default='')
 correction_of:Mapped[str]=mapped_column(String(80),nullable=True)
 note:Mapped[str]=mapped_column(Text,default='')
 author:Mapped[str]=mapped_column(String(160))
 created_at:Mapped[str]=mapped_column(String(64))
