from sqlalchemy import JSON
from sqlalchemy import Column, String, Boolean, Integer, PickleType
from database.connector import Base

class DBRunner(Base):
    __tablename__ = "runners"

    id = Column(String, primary_key=True, index=True)
    is_done = Column(Boolean, default=False)

class Task(Base):
    __tablename__="Tasks"
    id=Column(String,primary_key=True,index=True)
    initial_actions = Column(JSON)
    operation_description=Column(String)
    operation_steps=Column(String)
