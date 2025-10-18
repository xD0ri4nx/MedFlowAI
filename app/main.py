"""FastAPI Application with all routes"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from config import settings
from app.services.llm_service import get_llm_response
from app.services.supabase_service import supabase_service

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


class GenerateAlertRequest(BaseModel):
    """Request model for /gen_alert endpoint"""
    user_id: str = Field(..., description="UUID of the user to generate alert for")
    target_date: Optional[str] = Field(None, description="Date to analyze (YYYY-MM-DD format, default: today)")


class GenerateAlertResponse(BaseModel):
    """Response model for /gen_alert endpoint"""
    user_id: str = Field(..., description="User ID")
    date: str = Field(..., description="Date analyzed")
    summary: dict = Field(..., description="Health data summary")
    feedback: str = Field(..., description="AI-generated health feedback and recommendations")
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


@app.post("/gen_alert", response_model=GenerateAlertResponse)
async def generate_alert(request: GenerateAlertRequest):
    """
    Generate health alert and feedback for a user based on their daily health data.
    
    This endpoint:
    1. Fetches general health data for the user (consum, somn, vitale, sport)
    2. Creates a comprehensive summary
    3. Sends the summary to the LLM for analysis
    4. Returns AI-generated health feedback and recommendations
    
    Args:
        request: GenerateAlertRequest containing:
            - user_id: UUID of the user
            - target_date: Optional date to analyze (default: today)
    
    Returns:
        GenerateAlertResponse with summary and AI feedback
    
    Example:
        POST /gen_alert
        {
            "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "target_date": "2025-10-18"
        }
    """
    try:
        # Parse target date or use today
        if request.target_date:
            try:
                target_date = date.fromisoformat(request.target_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        else:
            target_date = date.today()
        
        # Step 1: Get daily summary from Supabase
        summary = supabase_service.get_daily_summary(
            user_id=request.user_id,
            target_date=target_date
        )
        
        # Check if user exists
        if not summary.get("profile"):
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {request.user_id} not found"
            )
        
        # Check if there's any data for this date
        if summary.get("total_records", 0) == 0:
            return GenerateAlertResponse(
                user_id=request.user_id,
                date=str(target_date),
                summary=summary,
                feedback="Nu există date înregistrate pentru această zi. Vă rugăm să adăugați date despre consum, somn, vitale și activitate fizică pentru a primi recomandări personalizate.",
                success=True
            )
        
        # Step 2: Create a detailed prompt for the LLM
        user_name = summary.get("profile", {}).get("full_name", "Utilizator")
        
        prompt = f"""Analizează datele medicale zilnice pentru {user_name} din data de {target_date}:

PROFIL PACIENT:
- Nume: {user_name}
- Data nașterii: {summary.get("profile", {}).get("date_of_birth", "N/A")}
- Telefon: {summary.get("profile", {}).get("phone", "N/A")}

DATE ZILNICE ({target_date}):

CONSUM (mese și lichide):
{_format_data_section(summary.get("consum", []))}

SOMN:
{_format_data_section(summary.get("somn", []))}

VITALE (tensiune, puls, oxigenare):
{_format_data_section(summary.get("vitale", []))}

SPORT (activitate fizică):
{_format_data_section(summary.get("sport", []))}

---

Te rog să analizezi aceste date și să oferi:
1. O evaluare generală a stării de sănătate pentru această zi
2. Alerte sau atenționări dacă există valori îngrijorătoare (tensiune anormală, oxigenare scăzută, somn insuficient, etc.)
3. Recomandări specifice pentru îmbunătățirea sănătății
4. Sfaturi personalizate bazate pe datele observate

Răspunde în limba română, într-un stil profesional dar prietenos, ca un asistent medical."""

        # Step 3: Get LLM feedback
        system_message = """Ești un asistent medical AI specializat în analiza datelor de sănătate. 
Analizezi date zilnice despre consum alimentar, somn, semne vitale și activitate fizică.
Oferi feedback constructiv, identifici potențiale probleme de sănătate și dai recomandări personalizate.
Răspunzi întotdeauna în limba română, într-un mod profesional dar accesibil."""

        feedback = get_llm_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=1000
        )
        
        return GenerateAlertResponse(
            user_id=request.user_id,
            date=str(target_date),
            summary=summary,
            feedback=feedback,
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate alert: {str(e)}"
        )


def _format_data_section(data_list):
    """Helper function to format data section for LLM prompt"""
    if not data_list:
        return "- Nu există date înregistrate"
    
    formatted = []
    for idx, item in enumerate(data_list, 1):
        details = item.get("details", {})
        if isinstance(details, dict):
            details_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
            formatted.append(f"  Înregistrare {idx}: {details_str}")
        else:
            formatted.append(f"  Înregistrare {idx}: {details}")
    
    return "\n".join(formatted) if formatted else "- Nu există date înregistrate"


@app.get("/api/v1/users")
async def get_all_users():
    """
    Get all user profiles.
    
    Returns:
        List of all user profiles in the system
    """
    try:
        profiles = supabase_service.get_all_profiles()
        return {
            "success": True,
            "count": len(profiles),
            "users": profiles
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch users: {str(e)}"
        )


@app.get("/api/v1/users/{user_id}/summary")
async def get_user_summary(user_id: str, target_date: Optional[str] = None):
    """
    Get daily health summary for a specific user.
    
    Args:
        user_id: UUID of the user
        target_date: Optional date (YYYY-MM-DD), defaults to today
    
    Returns:
        Comprehensive health data summary
    """
    try:
        # Parse date
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        else:
            parsed_date = date.today()
        
        summary = supabase_service.get_daily_summary(user_id, parsed_date)
        
        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch summary: {str(e)}"
        )


@app.get("/api/v1/cabinete")
async def get_all_cabinete():
    """
    Get all medical offices/clinics.
    
    Returns:
        List of all medical offices
    """
    try:
        cabinete = supabase_service.get_all_cabinete()
        return {
            "success": True,
            "count": len(cabinete),
            "cabinete": cabinete
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cabinete: {str(e)}"
        )


@app.get("/api/v1/users/{user_id}/programari")
async def get_user_appointments(user_id: str, active_only: bool = True):
    """
    Get user's appointments.
    
    Args:
        user_id: UUID of the user
        active_only: If true, return only active appointments (default: true)
    
    Returns:
        List of user's appointments with cabinet details
    """
    try:
        programari = supabase_service.get_user_programari(user_id, active_only)
        return {
            "success": True,
            "count": len(programari),
            "programari": programari
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch programari: {str(e)}"
        )

