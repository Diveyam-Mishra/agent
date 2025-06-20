import json
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, WebSocket
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio
import pandas as pd
import io
import os
import uuid
import time
from datetime import datetime

from database.connector import get_db
from controllers.task import process_excel_file
from model.Agent_input import *
from schema.TaskTracker import TaskTracker

router = APIRouter()



@router.post("/start", response_model=FileUploadResponse)
async def start_agent(
    executionId: str = Form(...),
    agentId: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    taskExcel: UploadFile = File(...),
    appType: str = Form(...),
    url: str = Form(...),
    db: Session = Depends(get_db)
):
    # Create sensitive data dictionary from individual fields
    sensitive_data_dict = {
        "email": email,
        "password": password
    }
    
    # Save the uploaded file content
    excel_content = await taskExcel.read()
    file_name = taskExcel.filename
    
    # Create a background task to process the Excel file
    asyncio.create_task(process_excel_file(
        excel_content=excel_content,
        file_name=file_name,
        execution_id=executionId,
        agent_id=agentId,
        app_type=appType,
        url=url,
        sensitive_data_dict=sensitive_data_dict,
        db=db
    ))
    
    # Return immediate response to client
    return {
        "status": "success",
        "message": f"File '{file_name}' uploaded successfully. Processing has started.",
        "execution_id": executionId,
        "agent_id": agentId
    }



@router.get("/is_done/{task_id}")
async def is_done(task_id: str, db: Session = Depends(get_db)):
    """
    Check if a task is complete using its row_task_id.
    """
    # Check TaskTracker for task status
    task_record = db.query(TaskTracker).filter(TaskTracker.row_task_id == task_id).first()
    if task_record:
        return {
            "is_done": task_record.status in ["Completed", "Failed"],
            "status": task_record.status,
            "duration": task_record.duration
        }
    
    return {"error": "Task not found"}


@router.get("/execution/{execution_id}/status", response_model=ExecutionStatus)
async def get_execution_status(execution_id: str, db: Session = Depends(get_db)):
    """
    Get the status of all tasks for a specific execution ID.
    """
    task_records = db.query(TaskTracker).filter(TaskTracker.execution_id == execution_id).all()
    
    if not task_records:
        return {"error": "No tasks found for this execution ID"}
    
    tasks = []
    for task in task_records:
        tasks.append({
            "row_task_id": task.row_task_id,
            "file_name": task.file_name,
            "agent_id": task.agent_id,
            "operation": task.operation,
            "status": task.status,
            "time_stamp": task.time_stamp.isoformat() if task.time_stamp else None,
            "duration": task.duration
        })
    
    # Calculate stats
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task["status"] == "Completed")
    failed_tasks = sum(1 for task in tasks if task["status"] == "Failed")
    pending_tasks = sum(1 for task in tasks if task["status"] == "Pending")
    running_tasks = sum(1 for task in tasks if task["status"] == "Running")
    
    return {
        "execution_id": execution_id,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "pending_tasks": pending_tasks,
        "running_tasks": running_tasks,
        "is_complete": pending_tasks == 0 and running_tasks == 0,
        "tasks": tasks
    }


@router.get("/task/{row_task_id}", response_model=TaskStatus)
async def get_task_status(row_task_id: str, db: Session = Depends(get_db)):
    """
    Get the status of a specific task by its row_task_id.
    """
    task = db.query(TaskTracker).filter(TaskTracker.row_task_id == row_task_id).first()
    
    if not task:
        return {"error": "Task not found"}
    
    return {
        "row_task_id": task.row_task_id,
        "execution_id": task.execution_id,
        "file_name": task.file_name,
        "agent_id": task.agent_id,
        "operation": task.operation,
        "status": task.status,
        "time_stamp": task.time_stamp.isoformat() if task.time_stamp else None,
        "duration": task.duration
    }

@router.get("/execution/{execution_id}/file/{file_name}", response_model=FileStatus)
async def get_file_status(execution_id: str, file_name: str, db: Session = Depends(get_db)):
    """
    Get the status of all tasks for a specific file within an execution ID.
    """
    # URL-decode the file_name if needed
    from urllib.parse import unquote
    file_name = unquote(file_name)
    
    task_records = db.query(TaskTracker).filter(
        TaskTracker.execution_id == execution_id,
        TaskTracker.file_name == file_name
    ).all()
    
    if not task_records:
        return {"error": f"No tasks found for file '{file_name}' in execution '{execution_id}'"}
    
    tasks = []
    for task in task_records:
        tasks.append({
            "row_task_id": task.row_task_id,
            "operation": task.operation,
            "status": task.status,
            "time_stamp": task.time_stamp.isoformat() if task.time_stamp else None,
            "duration": task.duration
        })
    
    # Calculate stats
    total_tasks = len(tasks)
    completed_tasks = sum(1 for task in tasks if task["status"] == "Completed")
    failed_tasks = sum(1 for task in tasks if task["status"] == "Failed")
    pending_tasks = sum(1 for task in tasks if task["status"] == "Pending")
    running_tasks = sum(1 for task in tasks if task["status"] == "Running")
    processing_tasks = sum(1 for task in tasks if task["status"] == "Processing")
    
    return {
        "execution_id": execution_id,
        "file_name": file_name,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "pending_tasks": pending_tasks,
        "running_tasks": running_tasks,
        "processing_tasks": processing_tasks,
        "is_complete": pending_tasks == 0 and running_tasks == 0 and processing_tasks == 0,
        "tasks": tasks
    }

@router.get("/executions", response_model=ExecutionsListResponse)
async def get_all_executions(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    """
    Get a list of all executions and their overall status.
    """
    # Get unique execution IDs
    execution_ids = db.query(TaskTracker.execution_id).distinct().offset(offset).limit(limit).all()
    
    if not execution_ids:
        return {"executions": []}
    
    executions = []
    for (execution_id,) in execution_ids:
        # Get execution stats
        stats = db.query(
            TaskTracker.status,
            db.func.count(TaskTracker.id).label('count')
        ).filter(
            TaskTracker.execution_id == execution_id
        ).group_by(TaskTracker.status).all()
        
        # Calculate status counts
        status_counts = {status: count for status, count in stats}
        total = sum(status_counts.values())
        
        # Get file names
        file_names = db.query(TaskTracker.file_name).filter(
            TaskTracker.execution_id == execution_id
        ).distinct().all()
        file_names = [name for (name,) in file_names]
        
        # Get agents
        agents = db.query(TaskTracker.agent_id).filter(
            TaskTracker.execution_id == execution_id
        ).distinct().all()
        agents = [agent for (agent,) in agents]
        
        # Calculate completion percentage
        completed = status_counts.get('Completed', 0)
        completion_percentage = (completed / total * 100) if total > 0 else 0
        
        executions.append({
            "execution_id": execution_id,
            "files": file_names,
            "agents": agents,
            "total_tasks": total,
            "status_counts": status_counts,
            "completion_percentage": round(completion_percentage, 2),
            "is_complete": total > 0 and (status_counts.get('Pending', 0) + 
                                          status_counts.get('Running', 0) + 
                                          status_counts.get('Processing', 0) == 0)
        })
    
    return {"executions": executions}

