from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import UploadFile
from typing import List, Dict
import pandas as pd

from database.connector import get_db
from schema.DBRunner import Task


async def task_finder(app_type: str, operation: str, db: Session = Depends(get_db)):
    """
    This function is a placeholder for the actual task finding logic.
    It should be implemented to find and return the task based on the provided parameters.
    """
    task_instructions= db.query(Task).filter(Task.id == app_type+"_"+operation).first()
    print(f"Task instructions found: {task_instructions}")
    return task_instructions

async def parse_excel(file: UploadFile) -> List[Dict]:
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
