from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio

from database import get_db
from controllers import create_agent_runner, start_agent_instance
from model.Agent_input import *

router = APIRouter()



@router.post("/start", response_model=StartResponse)
async def start_agent_endpoint(req: StartRequest, db: Session = Depends(get_db)):
    db_runner_record = create_agent_runner(db, req.task_excel, req.conversation_path)
    asyncio.create_task(start_agent_instance(db, db_runner_record))
    return {"session": db_runner_record.id}

