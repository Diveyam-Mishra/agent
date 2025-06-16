from pydantic import BaseModel

class StartRequest(BaseModel):
    task_excel: str
    conversation_path: str

class StartResponse(BaseModel):
    session: str