"""
Minimal test version - NO Firebase dependencies
Use this to test if the issue is with Firebase imports
"""
from fastapi import FastAPI
import uvicorn
import os

app = FastAPI(title="Minimal Test API")

@app.get("/")
def read_root():
    return {"message": "Minimal test API working"}

@app.get("/ping")
def ping():
    return {"status": "pong", "test": "minimal"}

@app.get("/health")
def health():
    return {
        "status": "healthy", 
        "test": "minimal",
        "port": os.environ.get("PORT", "not-set")
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)