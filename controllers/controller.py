import uuid
import asyncio
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from schema.DBRunner import DBRunner
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
        try:
            # Update DB state if necessary, e.g., runner started
            result = await _run_agent_logic(self.session_id,self.task, self.browser_session, self.sensitive_data)
            print(f"Agent run completed for session {self.session_id}, result: {result}")
            await self.queue.put({"result": result})
            print(f"Agent run completed successfully for session {self.session_id}")
        except Exception as e:
            print(f"Agent run failed for session {self.session_id}: {e}")
            await self.queue.put({"error": str(e)})
        finally:
            self.done = True
            db_runner = db.query(DBRunner).filter(DBRunner.id == self.session_id).first()
            if db_runner:
                db_runner.is_done = result.get("done") if isinstance(result, dict) else False
                db.commit()
            if self.session_id in global_active_runners:
                 del global_active_runners[self.session_id]

    async def next_update(self):
        return await self.queue.get()

async def browser_profile_opening_logic(): 
    browser_profile = BrowserProfile(
        headless=False,
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
    print("Agent task execution finished.")
    return {
            "final_result": result.final_result(),
            "urls": result.urls(),
            "errors": result.errors(),
            "model_thoughts": result.model_thoughts(),
            "done": result.is_done(),
            "session_id": session_id
        }

def create_agent_runner(db: Session):
    session_id = str(uuid.uuid4())
    print(f"Session {session_id} starting...")
    db_runner = DBRunner(id=session_id, is_done=False)
    db.add(db_runner)
    db.commit()
    db.refresh(db_runner)
    return session_id

    # merged_task_data = {
    #     "url": url,
    #     "task_description": task_instructions.operation_description,
    #     "instructions": task_instructions.operation_steps,
    #     "user_info": user_info,
    # }
    # # conversation_path="running/log/{task_id}"
    # session_id= create_agent_runner(db)
async def start_agent_instance(db: Session, session_id:str ,sensitive_data: dict, merged_task_data: dict):
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

