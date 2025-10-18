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
    user_id: str = Field(..., description="UUID of the user")
    question: str = Field(..., description="The user's health question or concern")


class AskResponse(BaseModel):
    """Response model for /ask endpoint"""
    result: str = Field(..., description="The LLM's personalized health feedback")
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
    Ask health-related questions and get personalized feedback based on your health data.

    This endpoint analyzes your health data (consumption, sleep, vitals, sports) and provides
    personalized feedback based on your specific question or concern.

    Args:
        request: AskRequest object containing:
            - user_id: UUID of the user
            - question: The user's health question or concern

    Returns:
        AskResponse: Object containing personalized health feedback and success status

    Example:
        POST /ask
        {
            "user_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
            "question": "De ce mă simt obosit?"
        }
    """
    try:
        # Step 1: Fetch user's health summary (all-time data)
        summary = supabase_service.get_daily_summary(
            user_id=request.user_id,
            target_date=date.today()  # Function gets all-time data regardless of date
        )

        # Check if user exists
        if not summary.get("profile"):
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {request.user_id} not found"
            )

        # Step 2: Build hardcoded system prompt
        system_message = """Ești un asistent medical AI care oferă feedback personalizat bazat pe datele de sănătate ale utilizatorului.
Analizezi rezumatul de sănătate al utilizatorului (consum alimentar, somn, semne vitale, activitate fizică) și răspunzi la întrebarea lor cu insight-uri relevante din datele lor. Trebuie sa fi dur si sa oferi raspunsuri scurte si la obiect. Daca nu stii sigur motivul recomanda consultarea unui medic specialist dar cu mentionarea scurta a unor posibile cauze in baza profilului utilizatorului si a datelor disponibile."""

        # Step 3: Format health summary for the prompt
        user_name = summary.get("profile", {}).get("full_name", "Utilizator")

        # Format each health data section
        health_summary = f"""PROFIL UTILIZATOR:
- Nume: {user_name}
- Data nașterii: {summary.get("profile", {}).get("date_of_birth", "N/A")}

DATE DE SĂNĂTATE:

CONSUM (mese și lichide):
{_format_data_section(summary.get("consum", []))}

SOMN:
{_format_data_section(summary.get("somn", []))}

VITALE (tensiune, puls, oxigenare):
{_format_data_section(summary.get("vitale", []))}

SPORT (activitate fizică):
{_format_data_section(summary.get("sport", []))}

MEDICAMENTE:
{_format_data_section(summary.get("medicamente", []))}"""

        # Step 4: Build user prompt combining question + health summary
        prompt = f"""Întrebarea utilizatorului: {request.question}

{health_summary}

---

Bazându-te pe datele de sănătate de mai sus, oferă un răspuns scurt și personalizat la întrebarea utilizatorului."""

        # Step 5: Call LLM with hardcoded parameters
        result = get_llm_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=500
        )

        return AskResponse(
            result=result,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get health feedback: {str(e)}"
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

