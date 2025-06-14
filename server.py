import sys
import asyncio
from asyncio import WindowsProactorEventLoopPolicy

# Ensure ProactorEventLoop for full subprocess support on Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
