import sys
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routes.router import router as api_router
from database.connector import engine, Base

# Create database tables
Base.metadata.create_all(bind=engine)

load_dotenv()

app = FastAPI()
ALLOWED_ORIGINS = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


async def _serve_app():
    config = uvicorn.Config(app=app, port=8000, reload=True)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(_serve_app())
