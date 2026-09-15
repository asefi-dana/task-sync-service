import os
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="Task Service API", version="1.0.0")

@app.get("/health")
@app.get("/")
def health():
    return {"status": "healthy", "service": "task-sync-worker"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
