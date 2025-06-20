from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

class StartRequest(BaseModel):
    executionId: str
    agentId: str
    email: str
    password: str
    appType: str
    operation: str
    url: str

class StartResponse(BaseModel):
    status: str
    message: str
    execution_id: str
    agent_id: str

class FileUploadResponse(BaseModel):
    status: str
    message: str
    execution_id: str
    agent_id: str

class TaskStatus(BaseModel):
    row_task_id: str
    operation: str
    status: str
    time_stamp: Optional[datetime] = None
    duration: float

class FileStatus(BaseModel):
    execution_id: str
    file_name: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    running_tasks: int
    processing_tasks: int
    is_complete: bool
    tasks: List[TaskStatus]

class ExecutionStatus(BaseModel):
    execution_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    pending_tasks: int
    running_tasks: int
    is_complete: bool
    tasks: List[TaskStatus]

class ExecutionSummary(BaseModel):
    execution_id: str
    files: List[str]
    agents: List[str]
    total_tasks: int
    status_counts: Dict[str, int]
    completion_percentage: float
    is_complete: bool

class ExecutionsListResponse(BaseModel):
    executions: List[ExecutionSummary]

class TaskData:
    def __init__(self, url: str, description: str, instructions: str, user_info: List[Dict],
                 execution_id: str = None, row_task_id: str = None):
        self.url = url
        self.description = description
        self.instructions = instructions
        self.user_info = user_info
        self.execution_id = execution_id
        self.row_task_id = row_task_id