"""FastAPI Application with all routes"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from config import settings
from app.services.llm_service import get_llm_response

# Request/Response Models
class AskRequest(BaseModel):
    """Request model for /ask endpoint"""
    prompt: str = Field(..., description="The main question or prompt to ask the LLM")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt to set context/behavior")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Controls randomness (0.0-2.0)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens in the response")


class AskResponse(BaseModel):
    """Response model for /ask endpoint"""
    result: str = Field(..., description="The LLM's response")
    success: bool = Field(..., description="Whether the request was successful")


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


@app.post("/ask", response_model=AskResponse)
async def ask_llm(request: AskRequest):
    """
    Ask the LLM a question with optional system prompt.

    This endpoint allows you to send a prompt to the OpenAI LLM and receive a response.
    You can optionally provide a system prompt to set the context or behavior.

    Args:
        request: AskRequest object containing:
            - prompt: The question/prompt to ask
            - system_prompt: Optional system message to set context
            - temperature: Optional temperature setting (0.0-2.0)
            - max_tokens: Optional maximum tokens in response

    Returns:
        AskResponse: Object containing the LLM's response and success status

    Example:
        POST /ask
        {
            "prompt": "What is diabetes?",
            "system_prompt": "You are a medical expert assistant"
        }
    """
    try:
        # Call the LLM service
        result = get_llm_response(
            prompt=request.prompt,
            system_message=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return AskResponse(
            result=result,
            success=True
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get LLM response: {str(e)}"
        )
