"""
Versión mínima para Railway testing - SIN Firebase initialization
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Crear instancia de FastAPI SIN lifespan
app = FastAPI(
    title="Gestor de Proyectos API - Railway Test",
    description="API para gestión de proyectos - Version mínima",
    version="1.0.0-test"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    """Endpoint raíz básico"""
    return {
        "message": "Gestor de Proyectos API - Railway Test",
        "version": "1.0.0-test",
        "timestamp": datetime.now().isoformat(),
        "port": os.getenv("PORT", "8000"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "status": "running"
    }

@app.get("/ping")
async def ping():
    """Health check super simple"""
    return {
        "status": "ok", 
        "timestamp": datetime.now().isoformat(),
        "port": os.getenv("PORT", "8000")
    }

@app.get("/health")
async def health_check():
    """Health check básico sin Firebase"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "api": "running"
        },
        "port": os.getenv("PORT", "8000"),
        "environment": os.getenv("ENVIRONMENT", "development")
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Starting minimal test server on port: {port}")
    uvicorn.run("main_test:app", host="0.0.0.0", port=port, reload=False)