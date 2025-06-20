from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database.connector import Base

class TaskTracker(Base):
    __tablename__ = "task_tracker"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String, index=True)
    file_name = Column(String)
    agent_id = Column(String, index=True)
    row_task_id = Column(String, index=True)
    operation = Column(String)
    status = Column(String)  # Pending, Completed, Failed, Running, etc.
    time_stamp = Column(DateTime, server_default=func.now())
    duration = Column(Float)  # Duration in seconds
