import os
import sys

# Disable tqdm progress bars globally to avoid console flush issues
os.environ["TQDM_DISABLE"] = "1"

# Workaround for Windows background task execution: ignore OSError on stream flush
orig_stderr_flush = sys.stderr.flush
def safe_stderr_flush():
    try:
        orig_stderr_flush()
    except OSError:
        pass
sys.stderr.flush = safe_stderr_flush

orig_stdout_flush = sys.stdout.flush
def safe_stdout_flush():
    try:
        orig_stdout_flush()
    except OSError:
        pass
sys.stdout.flush = safe_stdout_flush

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from api.routes import router

app = FastAPI(title="Resume Builder API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api", tags=["Resume"])

@app.get("/")
async def root():
    return {"message": "Resume Builder API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
