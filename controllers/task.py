import asyncio
from fastapi import Depends, UploadFile
from sqlalchemy.orm import Session
from typing import List, Dict, Optional, Any
import pandas as pd
import time
import uuid
from datetime import datetime

from controllers.controller import start_agent_instance
from database.connector import get_db
from schema.DBRunner import Task  # Still needed for task instructions
from schema.TaskTracker import TaskTracker


async def process_excel_file(
    excel_content: bytes,
    file_name: str,
    execution_id: str,
    agent_id: str,
    app_type: str,
    url: str,
    sensitive_data_dict: dict,
    db: Session
):
    """
    Process an Excel file in the background.
    This function is called as a background task to avoid blocking the API response.
    Each row is processed independently with its own operation, timing, and status tracking.
    """
    try:
        df = pd.read_excel(excel_content)
        
        task_count = 0
        header_row = df.iloc[0].to_dict()
          # Store all data rows for processing
        for index, row in df.iterrows():
            row_data = row.to_dict()
            print(f"Processing row {index + 1}: {row_data}")
            # Extract operation from row data or use the default
            row_operation = extract_operation_from_row(row_data)
            
            # Get task instructions for this specific row operation
            task_instructions = await task_finder(
                app_type=app_type,
                operation=row_operation,
                db=db
            )
            
            if not task_instructions:
                print(f"Warning: No task instructions found for app_type={app_type}, operation={row_operation}")
                continue
                
            row_task_id = str(uuid.uuid4())
            
            start_time = datetime.now()
            
            task_entry = TaskTracker(
                execution_id=execution_id,
                file_name=file_name,
                agent_id=agent_id,
                row_task_id=row_task_id,
                operation=row_operation,
                status="Pending",
                time_stamp=start_time,
                duration=0.0
            )
            db.add(task_entry)
            db.commit()
            db.refresh(task_entry)            # Format row data for the agent with header context
            user_info = []
            
            # Always include the header (first row) for context
            
            # If processing the header row itself, just include it once
            user_info.append(header_row)
                # For data rows, include both header and the current row
                  # Add header row first for context
            user_info.append(row_data)    # Add current data row
            print(f"User info for row {index + 1}: {user_info}")
            # Prepare task data for the agent
            merged_task_data = {
                "url": url,
                "task_description": task_instructions.operation_description,
                "instructions": task_instructions.operation_steps,
                "user_info": user_info,
                "execution_id": execution_id,
                "row_task_id": row_task_id,
                "operation": row_operation         # Include row index for reference
            }
            
            # Update task tracker status to Running
            task_entry.status = "Running"
            db.commit()
            
            # Start agent instance for this row using row_task_id directly
            asyncio.create_task(start_agent_instance(
                db=db, 
                session_id=row_task_id,  # Use row_task_id directly as the session ID
                sensitive_data=sensitive_data_dict,
                merged_task_data=merged_task_data
            ))
            
            task_count += 1
        
        # Generate a summary of the processing (this doesn't create a database entry)
        print(f"Initiated processing of {task_count} rows from file {file_name} for execution {execution_id}")
        print(f"Each row will be processed independently with its own status tracking.")
        print(f"Check execution status at /execution/{execution_id}/status")
        
    except Exception as e:
        print(f"Error processing Excel file: {e}")
        # Mark all pending tasks as failed
        db.query(TaskTracker).filter(
            TaskTracker.execution_id == execution_id,
            TaskTracker.file_name == file_name,
            TaskTracker.agent_id == agent_id,
            TaskTracker.status == "Pending"
        ).update({"status": "Failed"})
        db.commit()







async def task_finder(app_type: str, operation: str, db: Session = Depends(get_db)):
    """
    Find task instructions based on application type and operation.
    """
    task_id = f"{app_type}_{operation}" if operation else app_type
    task_instructions = db.query(Task).filter(Task.id == task_id).first()
    print(f"Task finder: Looking for task with ID '{task_id}'")
    print(f"Task instructions found: {task_instructions}")
    return task_instructions

async def parse_excel(file: UploadFile) -> List[Dict]:
    """
    Parse an Excel file and return all data as a list of dictionaries.
    """
    contents = await file.read()
    excel = pd.read_excel(contents, sheet_name=None)
    all_data = []
    for sheet_name, df in excel.items():
        df = df.fillna("").astype(str)
        records = df.to_dict(orient="records")
        for record in records:
            cleaned = {k.strip(): v.strip() for k, v in record.items() if v.strip() != ""}
            all_data.append(cleaned)
    return all_data

async def process_excel_row(
    db: Session,
    execution_id: str,
    agent_id: str,
    file_name: str,
    row_data: Dict[str, Any],
    default_operation: str = None
) -> tuple:
    """
    Process a single row from an Excel file and create a task tracker entry.
    
    Args:
        db: Database session
        execution_id: Execution ID
        agent_id: Agent ID
        file_name: File name
        row_data: Row data from Excel
        default_operation: Default operation if not found in row_data
        
    Returns:
        A tuple containing (row_task_id, task_entry_id, operation)
    """
    row_task_id = str(uuid.uuid4())
    
    # Extract operation from row data or use default
    operation = extract_operation_from_row(row_data, default_operation)
    
    # Create a task tracker entry with current timestamp for accurate duration tracking
    task_entry = TaskTracker(
        execution_id=execution_id,
        file_name=file_name,
        agent_id=agent_id,
        row_task_id=row_task_id,
        operation=operation,
        status="Pending",
        duration=0.0,
        time_stamp=datetime.now()  # Use datetime object for proper timestamp
    )
    
    db.add(task_entry)
    db.commit()
    db.refresh(task_entry)
    
    return row_task_id, task_entry.id, operation

async def update_task_status(
    db: Session,
    row_task_id: str,
    status: str,
    duration: Optional[float] = None
):
    """
    Update the status and optionally duration of a task in the task tracker.
    If duration is not provided, it will be calculated based on the start time.
    """
    task_entry = db.query(TaskTracker).filter(TaskTracker.row_task_id == row_task_id).first()
    
    if task_entry:
        task_entry.status = status
        
        # If duration is provided, use it directly
        if duration is not None:
            task_entry.duration = duration
        # Otherwise, calculate duration if this is a terminal status (Completed or Failed)
        elif status in ["Completed", "Failed"] and task_entry.time_stamp:
            # Calculate the duration based on start timestamp
            if isinstance(task_entry.time_stamp, datetime):
                task_entry.duration = (datetime.now() - task_entry.time_stamp).total_seconds()
            elif isinstance(task_entry.time_stamp, float):
                task_entry.duration = time.time() - task_entry.time_stamp
        
        db.commit()
        return True
    
    return False

def extract_operation_from_row(row_data: Dict[str, Any], default_operation: str = None) -> str:
    """
    Extract the operation from the row data.
    Looks for keys like 'operation', 'Operation', 'task', 'Task', 'action', 'Action'.
    
    Args:
        row_data: Dictionary containing the row data
        default_operation: Default operation to return if not found in row_data
        
    Returns:
        The operation string from the row data or the default_operation
    """
    possible_keys = ['operation', 'Operation']

    for key in possible_keys:
        if key in row_data and row_data[key]:
            return str(row_data[key]).strip()
    
    # If not found, return the default operation
    return default_operation
