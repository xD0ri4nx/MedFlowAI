"""FastAPI Application with all routes"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings

app = FastAPI(
    title="MedFlowAI",
    description="Medical AI Flow Management System",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to MedFlowAI",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MedFlowAI"
    }


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint"""
    return {
        "api_version": "v1",
        "status": "operational",
        "environment": settings.ENVIRONMENT
    }


@app.get("/api/v1/debug")
async def debug_info():
    """Debug endpoint - displays environment variables"""
    return {
        "project_name": settings.APP_NAME,
        "debug_mode": settings.DEBUG,
        "environment": settings.ENVIRONMENT,
        "host": settings.HOST,
        "port": settings.PORT
    }
