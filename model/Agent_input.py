from pydantic import BaseModel
from typing import List, Dict
class StartRequest(BaseModel):

    task_excel: str
    conversation_path: str

class StartResponse(BaseModel):
    session: str

class TaskData:
    def __init__(self, url: str, description: str, instructions: str, user_info: List[Dict]):
        self.url = url
        self.description = description
        self.instructions = instructions
        self.user_info = user_info