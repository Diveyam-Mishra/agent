import os
import sys
import uuid
import asyncio
import logging
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from asyncio import WindowsProactorEventLoopPolicy
from langchain_openai import ChatOpenAI
from browser_use import BrowserSession, BrowserProfile, Agent
import uvicorn

# Windows-specific setup
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())

load_dotenv()

# FastAPI setup
app = FastAPI()
ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runners = {}  # session_id -> AgentRunner

# --------- LOGGING SETUP ---------
def get_logger(session_id: str) -> logging.Logger:
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{session_id}.log")

    logger = logging.getLogger(session_id)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(log_path)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

# --------- AGENT RUNNER ---------
class AgentRunner:
    def __init__(self, task_excel: str, conversation_path: str, browser_session, logger: logging.Logger):
        self.task_excel = task_excel
        self.conversation_path = conversation_path
        self.browser_session = browser_session
        self.queue = asyncio.Queue()
        self.done = False
        self.logger = logger

    async def run(self):
        self.logger.info("Agent run initiated.")
        try:
            result = await _run_agent(self.task_excel, self.conversation_path, self.browser_session, self.logger)
            await self.queue.put({"result": result})
            self.logger.info("Agent run completed successfully.")
        except Exception as e:
            self.logger.exception("Agent run failed.")
            await self.queue.put({"error": str(e)})
        finally:
            self.done = True

    async def next_update(self):
        return await self.queue.get()

    async def control(self, msg: str):
        pass

# --------- SCHEMA ---------
class StartRequest(BaseModel):
    task_excel: str
    conversation_path: str

# --------- BROWSER SETUP ---------
async def browser_profile_opening():
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

# --------- AGENT EXECUTION ---------
async def _run_agent(task_excel: str, conversation_path: str, browser_session: BrowserSession, logger: logging.Logger):
    logger.info("Loading Excel task file.")
    task = pd.read_excel(task_excel)
    logger.info("Setting up LLMs and agent.")
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
        task_id="1",
        extend_system_message="""
You are a web automation agent that follows instructions with high precision. When navigating menus or clicking sidebar items, always prefer exact text matches over partial matches.
If multiple options have similar names, use the one that best aligns with the task intent (e.g., 'Access' vs. 'Privileged Access').
If you are asked to navigate to a specific page with a URL and can't find a relevant button to click, directly go_to_url.
If navigation to a different page URL is given, skip the UI step and directly use the URL.
Avoid assumptions based on position or styling alone—use label text and heading confirmation.
If a click or action changes the URL, use the new URL directly in the next step.
Skip any irrelevant or unfilled fields.
DOM structure may change, so rely on text content, not HTML structure.
If something is not visible, use "extract_content":"should_strip_link_urls":false to pull information.
You don't have to fill every field in a form—only the ones shown or required.
"""
    )

    logger.info("Executing agent task.")
    result = await agent.run()
    await agent.close()
    logger.info("Agent task execution finished.")
    return result

# --------- ROUTES ---------
@app.post("/start")
async def start_agent(req: StartRequest):
    browser_session = await browser_profile_opening()
    session_id = str(uuid.uuid4())
    logger = get_logger(session_id)
    logger.info(f"Session {session_id} started.")

    runner = AgentRunner(req.task_excel, req.conversation_path, browser_session, logger)
    runners[session_id] = runner

    asyncio.create_task(runner.run())
    return {"session": session_id}

@app.websocket("/ws/{session_id}")
async def agent_ws(ws: WebSocket, session_id: str):
    await ws.accept()
    if session_id not in runners:
        await ws.close()
        return
    runner = runners[session_id]
    try:
        while True:
            update = await runner.next_update()
            await ws.send_json(update)
            if runner.done:
                await ws.close()
                break
    except WebSocketDisconnect:
        pass

# --------- APP SERVE ---------
async def _serve_app():
    config = uvicorn.Config(app=app, port=8000, reload=True)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(_serve_app())
    except (NotImplementedError, RuntimeError):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def proactor_wrap():
            await _serve_app()
            loop.stop()
        loop.create_task(proactor_wrap())
        loop.run_forever()
