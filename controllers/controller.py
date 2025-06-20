import uuid
import asyncio
import pandas as pd
import time
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from schema.TaskTracker import TaskTracker
from browser_use import BrowserSession, BrowserProfile, Agent
from langchain_openai import ChatOpenAI

global_active_runners = {}

class AgentRunner:
    def __init__(self, session_id: str, task: str, browser_session, sensitive_data: dict):
        self.session_id = session_id
        self.task = task
        self.browser_session = browser_session
        self.sensitive_data = sensitive_data
        self.queue = asyncio.Queue()
        self.done = False
        
    async def run(self, db: Session):
        print(f"Agent run initiated for session {self.session_id}")
        result = None
        task_tracker = None
        
        try:
            task_tracker = db.query(TaskTracker).filter(TaskTracker.row_task_id == self.session_id).first()
            if task_tracker:
                task_tracker.status = "Running"
                db.commit()
        
            result = await _run_agent_logic(self.session_id, self.task, self.browser_session, self.sensitive_data)
            print(f"Agent run completed for session {self.session_id}")
            await self.queue.put({"result": result})
            
            # Update task status to completed in the task table
            if task_tracker:
                print(result.get("done", False) if isinstance(result, dict) else False)
                is_successful = result.get("done", False) if isinstance(result, dict) else False
                task_tracker.status = "Completed" if is_successful else "Failed"
                db.commit()
                
            print(f"Agent run completed successfully for session {self.session_id}")
            
        except Exception as e:
            print(f"Agent run failed for session {self.session_id}: {e}")
            await self.queue.put({"error": str(e)})
            
            # Update task status to failed if exception occurred
            if task_tracker:
                task_tracker.status = "Failed"
                db.commit()
                
        finally:
            self.done = True
            
            # Handle result even if it's None in case of exceptions
            is_successful = False
            if result:
                is_successful = result.get("done", False) if isinstance(result, dict) else False
            
            # Update task status in TaskTracker using row_task_id
            row_task_id = self.task.get("row_task_id", self.session_id)
            task_tracker = db.query(TaskTracker).filter(TaskTracker.row_task_id == row_task_id).first()
            
            if task_tracker:
                end_time = time.time()
                
                # Calculate duration based on the timestamp format
                if task_tracker.time_stamp:
                    if isinstance(task_tracker.time_stamp, datetime):
                        duration = (datetime.now() - task_tracker.time_stamp).total_seconds()
                    elif isinstance(task_tracker.time_stamp, float):
                        duration = end_time - task_tracker.time_stamp
                    else:
                        try:
                            if isinstance(task_tracker.time_stamp, datetime):
                                duration = end_time - task_tracker.time_stamp.timestamp()
                            elif isinstance(task_tracker.time_stamp, (int, float)):
                                duration = end_time - float(task_tracker.time_stamp)
                            else:
                                duration = 0
                        except:
                            duration = 0
                    
                    task_tracker.duration = duration
                
                # Update status (if not already updated)
                if task_tracker.status in ["Pending", "Running"]:
                    task_tracker.status = "Completed" if is_successful else "Failed"
                    db.commit()
            
            # Remove from global runners tracking
            if self.session_id in global_active_runners:
                del global_active_runners[self.session_id]

    async def next_update(self):
        return await self.queue.get()

async def browser_profile_opening_logic(): 
    browser_profile = BrowserProfile(
        headless=False,
        keep_alive=True,
        wait_for_network_idle_page_load_time=3.0,
        viewport={"width": 1280, "height": 1100},
        highlight_elements=True,
        viewport_expansion=500,
        user_data_dir=None,
        browser_binary_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        disable_security=True
    )
    browser_session = BrowserSession(browser_profile=browser_profile)
    await browser_session.start()
    return browser_session

async def _run_agent_logic(session_id:str,
                           task: dict, 
                           browser_session: BrowserSession, 
                           sensitive_data: dict):
    print("Setting up LLMs and agent.")
    llm = ChatOpenAI(model='gpt-4.1')
    print(task)
    agent = Agent(
        task=task,
        save_conversation_path=f"running/log/{session_id}", 
        browser_session=browser_session,
        llm=ChatOpenAI(model='gpt-4.1', temperature=0.4),
        planner_llm=llm,
        page_extraction_llm=ChatOpenAI(model='gpt-4.1'),
        use_vision=True,
        max_actions_per_step=5,
        max_input_tokens=136000,
        sensitive_data=sensitive_data,
        task_id=session_id,
        extend_system_message='''
You are a web automation agent that follows instructions with high precision. When navigating menus or clicking sidebar items, always prefer exact text matches over partial matches.
If multiple options have similar names, use the one that best aligns with the task intent (e.g., 'Access' vs. 'Privileged Access').
If you are asked to navigate to a specific page with a URL and can\'t find a relevant button to click, directly go_to_url.
If navigation to a different page URL is given, skip the UI step and directly use the URL.
Avoid assumptions based on position or styling alone—use label text and heading confirmation.
If a click or action changes the URL, use the new URL directly in the next step.
Skip any irrelevant or unfilled fields.
DOM structure may change, so rely on text content, not HTML structure.
If something is not visible, use "extract_content":"should_strip_link_urls":false to pull information.
You don\'t have to fill every field in a form—only the ones shown or required.
If a detail is automatically filled in a form, you can skip it.
'''
    )

    print("Executing agent task.")
    result = await agent.run()
    await agent.close()
    print("Agent task execution finished.")    # Extract row_task_id from the task data if available
    row_task_id = task.get("row_task_id", session_id)
    print("-----------------------------------------------------------------------")
    print("-----------------------------------------------------------------------")
    print("-----------------------------------------------------------------------")
    print("-----------------------------------------------------------------------")
    print("-----------------------------------------------------------------------")
    print(result.is_done())
    return {
            "final_result": result.final_result(),
            "urls": result.urls(),
            "errors": result.errors(),
            "model_thoughts": result.model_thoughts(),
            "done": result.is_done(),
            "session_id": session_id,
            "row_task_id": row_task_id
        }


async def start_agent_instance(db: Session, session_id:str, sensitive_data: dict, merged_task_data: dict):
    """Starts the browser and the agent runner instance asynchronously."""
    
    browser_session = await browser_profile_opening_logic()
    
    runner = AgentRunner(
        session_id=session_id,
        browser_session=browser_session,
        sensitive_data=sensitive_data,
        task=merged_task_data
    )
    
    global_active_runners[session_id] = runner
    
    asyncio.create_task(runner.run(db))
    print(f"Agent runner for session {session_id} created and task started in background.")
    

