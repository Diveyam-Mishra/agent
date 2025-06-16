import sys
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from asyncio import WindowsProactorEventLoopPolicy
import uvicorn

# Import the new router from routes.py
from routes import router as api_router
from database import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

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

# Include the router from routes.py
app.include_router(api_router)


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
