import json
from typing import Dict, List
from fastapi import APIRouter, Depends, File, Form, UploadFile, WebSocket
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio
import pandas as pd
import io

from database.connector import get_db
from controllers.controller import create_agent_runner, start_agent_instance
from controllers.task import task_finder, parse_excel
from model.Agent_input import *
from schema.DBRunner import DBRunner

router = APIRouter()



@router.post("/start")
async def start_agent(
    task_excel: UploadFile = File(...),
    app_type: str = Form(...),
    operation: str = Form(...),
    url: str = Form(...),
    sensitive_data: str = Form(...),
    db: Session = Depends(get_db)
):
    sensitive_data_dict = json.loads(sensitive_data)
    
    user_info = await parse_excel(task_excel)

    task_instructions=await task_finder(
        app_type=app_type,
        operation=operation,
        db=db
    )

    merged_task_data = {
        "url": url,
        "task_description": task_instructions.operation_description,
        "instructions": task_instructions.operation_steps,
        "user_info": user_info,
    }

    # conversation_path="running/log/{task_id}"
    session_id= create_agent_runner(db)


    asyncio.create_task(start_agent_instance(db, session_id,sensitive_data_dict,merged_task_data))
    return {"session": session_id}



@router.get("/is_done/{session_id}")
async def is_done(session_id: str, db: Session = Depends(get_db)):
    db_runner_record = db.query(DBRunner).filter(DBRunner.id == session_id).first()
    if not db_runner_record:
        return {"error": "Session not found"}
    
    return {"is_done": db_runner_record.is_done}



# @router.post("/start", response_model=StartResponse)
# async def start_agent_endpoint(req: StartRequest, db: Session = Depends(get_db)):
#     db_runner_record = create_agent_runner(db, req.task_excel, req.conversation_path)
#     asyncio.create_task(start_agent_instance(db, db_runner_record))
#     return {"session": db_runner_record.id}

