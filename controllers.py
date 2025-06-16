import uuid
import asyncio
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from models import DBRunner
from browser_use import BrowserSession, BrowserProfile, Agent
from langchain_openai import ChatOpenAI

global_active_runners = {}

class AgentRunner:
    def __init__(self, session_id: str, task_excel: str, conversation_path: str, browser_session):
        self.session_id = session_id
        self.task_excel = task_excel
        self.conversation_path = conversation_path
        self.browser_session = browser_session
        self.queue = asyncio.Queue()
        self.done = False
    async def run(self, db: Session):
        print(f"Agent run initiated for session {self.session_id}")
        try:
            # Update DB state if necessary, e.g., runner started
            result = await _run_agent_logic(self.session_id,self.task_excel, self.conversation_path, self.browser_session)
            await self.queue.put({"result": result})
            print(f"Agent run completed successfully for session {self.session_id}")
        except Exception as e:
            print(f"Agent run failed for session {self.session_id}: {e}")
            await self.queue.put({"error": str(e)})
        finally:
            self.done = True
            db_runner = db.query(DBRunner).filter(DBRunner.id == self.session_id).first()
            if db_runner:
                db_runner.is_done = True
                db.commit()
            if self.session_id in global_active_runners:
                 del global_active_runners[self.session_id] # Clean up from active runners

    async def next_update(self):
        return await self.queue.get()

async def browser_profile_opening_logic(): # Renamed to avoid conflict
    browser_profile = BrowserProfile(
        headless=False,
        wait_for_network_idle_page_load_time=3.0,
        viewport={"width": 1280, "height": 1100},
        locale='en-US',
        highlight_elements=True,
        viewport_expansion=-1,
        user_data_dir=None,
        browser_binary_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        disable_security=True
    )
    browser_session = BrowserSession(browser_profile=browser_profile)
    await browser_session.start()
    return browser_session

async def _run_agent_logic(session_id:str,task_excel: str, conversation_path: str, browser_session: BrowserSession):
    print("Loading Excel task file.")
    task = pd.read_excel(task_excel)
    print("Setting up LLMs and agent.")
    llm = ChatOpenAI(model='gpt-4.1')

    agent = Agent(
        task=task,
        save_conversation_path=conversation_path,
        browser_session=browser_session,
        llm=ChatOpenAI(model='gpt-4.1', temperature=0.4),
        planner_llm=llm,
        page_extraction_llm=ChatOpenAI(model='gpt-4.1'),
        use_vision=True,
        max_actions_per_step=5,
        max_input_tokens=136000,
        sensitive_data={
            'login_email': 'dmishra930@agentforce.com',
            'login_password': 'Divey@m02'
        },
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
'''
    )

    print("Executing agent task.")
    result = await agent.run()
    await agent.close()
    print("Agent task execution finished.")
    return result

def create_agent_runner(db: Session, task_excel: str, conversation_path: str):
    session_id = str(uuid.uuid4())
    print(f"Session {session_id} starting...")
    db_runner = DBRunner(id=session_id, task_excel=task_excel, conversation_path=conversation_path, is_done=False)
    db.add(db_runner)
    db.commit()
    db.refresh(db_runner)

    # This part needs to be async, so we'll call it from an async route handler
    # browser_session = await browser_profile_opening_logic()
    # runner = AgentRunner(session_id=session_id, task_excel=task_excel, conversation_path=conversation_path, browser_session=browser_session)
    # global_active_runners[session_id] = runner
    # asyncio.create_task(runner.run(db))
    return db_runner # Return the database model instance

async def start_agent_instance(db: Session, db_runner: DBRunner):
    """Starts the browser and the agent runner instance asynchronously."""
    browser_session = await browser_profile_opening_logic()
    runner = AgentRunner(
        session_id=db_runner.id,
        task_excel=db_runner.task_excel,
        conversation_path=db_runner.conversation_path,
        browser_session=browser_session
    )
    global_active_runners[db_runner.id] = runner
    asyncio.create_task(runner.run(db))
    print(f"Agent runner for session {db_runner.id} created and task started in background.")

