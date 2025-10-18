"""FastAPI Application with all routes"""
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from pathlib import Path
from config import settings
from app.services.llm_service import get_llm_response
from app.services.supabase_service import supabase_service

# Setup templates
BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Request/Response Models
class AskRequest(BaseModel):
    """Request model for /ask endpoint"""
    user_id: str = Field(..., description="UUID of the user")
    question: str = Field(..., description="The user's health question or concern")


class AskResponse(BaseModel):
    """Response model for /ask endpoint"""
    user_id: str = Field(..., description="UUID of the user")
    question: str = Field(..., description="The user's original question")
    generated_feedback: str = Field(..., description="The LLM's personalized health feedback")
    summary: dict = Field(..., description="Complete health summary from database")
    success: bool = Field(..., description="Whether the request was successful")


class ScheduleAppointmentRequest(BaseModel):
    """Request model for /schedule_appointment endpoint"""
    user_id: str = Field(..., description="UUID of the user")
    question: str = Field(..., description="The user's original health question")
    generated_feedback: str = Field(..., description="AI-generated health feedback")
    summary: dict = Field(..., description="Complete health summary from database")


class ScheduleAppointmentResponse(BaseModel):
    """Response model for /schedule_appointment endpoint"""
    success: bool = Field(..., description="Whether the request was successful")
    selected_clinic: dict = Field(..., description="Details of the selected clinic")
    message: str = Field(..., description="Confirmation message")


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

# Mount static files for assets (images, etc.)
app.mount("/assets", StaticFiles(directory=str(BASE_DIR / "assets")), name="assets")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint - redirects to home"""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/home", response_class=HTMLResponse)
async def home_page(request: Request):
    """Home page with health status dashboard"""
    return templates.TemplateResponse("home.html", {"request": request})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat page for AI health assistant"""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/add-data", response_class=HTMLResponse)
async def add_data_page(request: Request):
    """Add health data page"""
    return templates.TemplateResponse("add-data.html", {"request": request})


@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request):
    """Schedule appointment page"""
    return templates.TemplateResponse("schedule.html", {"request": request})


@app.get("/templates/appointment_email.html", response_class=HTMLResponse)
async def get_appointment_email_template():
    """Serve raw appointment email template for JavaScript to fetch"""
    template_path = BASE_DIR / "templates" / "appointment_email.html"
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return HTMLResponse(content=content)


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
async def ask_llm(request: Request, user_id: Optional[str] = Form(None), question: Optional[str] = Form(None)):
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
        # Parse incoming data - support JSON body or form-encoded (HTMX)
        body = None
        try:
            content_type = request.headers.get('content-type', '')
            if content_type.startswith('application/json'):
                body = await request.json()
            else:
                # Try form data (htmx submits form-encoded)
                form = await request.form()
                body = dict(form)
        except Exception:
            # Fallback to FastAPI-extracted form params
            body = {"user_id": user_id, "question": question}

        # Validate required fields via Pydantic model
        try:
            ask_req = AskRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

        # Step 1: Fetch user's health summary (all-time data)
        summary = supabase_service.get_daily_summary(
            user_id=ask_req.user_id,
            target_date=date.today()  # Function gets all-time data regardless of date
        )

        # Check if user exists
        if not summary.get("profile"):
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {ask_req.user_id} not found"
            )

        # Step 2: Build hardcoded system prompt
        system_message = """You are a medical AI assistant that provides personalized feedback based on user health data.
You analyze the user's health summary (food consumption, sleep, vital signs, physical activity) and respond to their questions with relevant insights from their data. You should be direct and provide short, concise answers. If you're not sure about the cause, recommend consulting a specialist doctor but briefly mention possible causes based on the user's profile and available data."""

        # Step 3: Format health summary for the prompt
        user_name = summary.get("profile", {}).get("full_name", "User")

        # Format each health data section
        health_summary = f"""USER PROFILE:
- Name: {user_name}
- Date of Birth: {summary.get("profile", {}).get("date_of_birth", "N/A")}

HEALTH DATA:

CONSUMPTION (meals and liquids):
{_format_data_section(summary.get("consum", []))}

SLEEP:
{_format_data_section(summary.get("somn", []))}

VITALS (blood pressure, pulse, oxygen):
{_format_data_section(summary.get("vitale", []))}

SPORTS (physical activity):
{_format_data_section(summary.get("sport", []))}

MEDICATION:
{_format_data_section(summary.get("medicamente", []))}"""

        # Step 4: Build user prompt combining question + health summary
        prompt = f"""User's question: {ask_req.question}

{health_summary}

---

Based on the health data above, provide a short and personalized response to the user's question."""

        # Step 5: Call LLM with hardcoded parameters
        result = get_llm_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=500
        )

        # Step 6: Return full context object for UI
        return AskResponse(
            user_id=ask_req.user_id,
            question=ask_req.question,
            generated_feedback=result,
            summary=summary,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get health feedback: {str(e)}"
        )


@app.get("/api/v1/generate_alert")
async def api_generate_alert(user_id: str, target_date: Optional[str] = None):
    """
    API endpoint to generate health alert for a user.
    
    Query params:
        - user_id: UUID of the user
        - target_date: Optional date (YYYY-MM-DD), defaults to today
    """
    try:
        from app.services.scheduler_service import generate_alert_for_user
        from datetime import date
        
        # Parse target date
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            parsed_date = None
        
        # Call the scheduler service function
        result = await generate_alert_for_user(user_id, parsed_date)
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Failed to generate alert"))
        
        # Generate brief summaries for each category using LLM
        summary = result.get("summary", {})
        brief_summaries = {}
        
        for category in ["consum", "somn", "vitale", "sport"]:
            data = summary.get(category, [])
            if data and len(data) > 0:
                # Create a brief prompt for each category
                details_str = "\n".join([f"- {item.get('details', {})}" for item in data[:3]])  # Limit to first 3 records
                
                category_names = {
                    "consum": "Nutriție",
                    "somn": "Somn", 
                    "vitale": "Semne vitale",
                    "sport": "Activitate fizică"
                }
                
                prompt = f"""Rezumă foarte scurt aceste date de {category_names[category]} în maximum 6-8 cuvinte în limba română:
{details_str}

Exemplu răspuns: "2 mese, 1.5L apă" sau "7h somn bun" sau "BP: 120/80, HR: 72" sau "30min alergare"
Răspunde DOAR cu rezumatul, fără alte cuvinte."""

                try:
                    brief_summary = get_llm_response(
                        prompt=prompt,
                        system_message="Ești un asistent care rezumă date medicale foarte concis.",
                        temperature=0.3,
                        max_tokens=30
                    ).strip()
                    brief_summaries[category] = brief_summary
                except:
                    brief_summaries[category] = f"{len(data)} înregistrări"
            else:
                brief_summaries[category] = "Fără date"
        
        result["brief_summaries"] = brief_summaries
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate alert: {str(e)}")


@app.post("/gen_alert", response_model=GenerateAlertResponse)
async def generate_alert(request: Request, user_id: Optional[str] = Form(None), target_date: Optional[str] = Form(None)):
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
        # Parse incoming data - support JSON body or form-encoded (HTMX)
        body = None
        try:
            content_type = request.headers.get('content-type', '')
            if content_type.startswith('application/json'):
                body = await request.json()
            else:
                form = await request.form()
                body = dict(form)
        except Exception:
            body = {"user_id": user_id, "target_date": target_date}

        # Validate via Pydantic
        try:
            gen_req = GenerateAlertRequest(**body)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request data: {str(e)}")

        # Parse target date or use today
        if gen_req.target_date:
            try:
                target_date = date.fromisoformat(gen_req.target_date)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        else:
            target_date = date.today()
        
        # Step 1: Get daily summary from Supabase
        summary = supabase_service.get_daily_summary(
            user_id=gen_req.user_id,
            target_date=target_date
        )
        
        # Check if user exists
        if not summary.get("profile"):
            raise HTTPException(
                status_code=404,
                detail=f"User with ID {gen_req.user_id} not found"
            )
        
        # Check if there's any data for this date
        if summary.get("total_records", 0) == 0:
            return GenerateAlertResponse(
                user_id=gen_req.user_id,
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
            user_id=gen_req.user_id,
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
        return "- No data recorded"

    formatted = []
    for idx, item in enumerate(data_list, 1):
        details = item.get("details", {})
        if isinstance(details, dict):
            details_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
            formatted.append(f"  Record {idx}: {details_str}")
        else:
            formatted.append(f"  Record {idx}: {details}")

    return "\n".join(formatted) if formatted else "- No data recorded"


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


@app.post("/api/v1/recommend_clinic")
async def recommend_clinic(request: Request):
    """
    Use LLM to recommend best clinic based on patient health data and chat history.

    Request body:
        - user_id: UUID of the user
        - chat_history: Array of chat messages
        - target_date: Optional date (YYYY-MM-DD)

    Returns:
        - profile: Patient profile data
        - recommended_clinics: Ranked list of clinics
        - reasoning: LLM explanation for top recommendations
    """
    try:
        from datetime import date

        body = await request.json()
        user_id = body.get('user_id')
        chat_history = body.get('chat_history', [])
        target_date_str = body.get('target_date')

        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")

        # Parse target date
        if target_date_str:
            try:
                target_date = date.fromisoformat(target_date_str)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format")
        else:
            target_date = date.today()

        # Get health data
        summary = supabase_service.get_daily_summary(user_id, target_date)
        profile = summary.get('profile', {})

        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        # Get all clinics
        cabinete = supabase_service.get_all_cabinete()

        if not cabinete:
            raise HTTPException(status_code=404, detail="No clinics available")

        # Format chat history for LLM
        chat_text = '\n'.join([
            f"{'Patient' if msg.get('role') == 'user' else 'AI'}: {msg.get('content', '')}"
            for msg in chat_history
        ])

        # Format health data
        health_summary_text = f"""
Nutrition: {len(summary.get('consum', []))} records
Sleep: {len(summary.get('somn', []))} records
Vitals: {len(summary.get('vitale', []))} records
Activity: {len(summary.get('sport', []))} records
"""

        # Format clinics for LLM
        clinics_text = '\n'.join([
            f"- {clinic.get('nume', 'N/A')} (Category: {clinic.get('categorie', 'General')})"
            for clinic in cabinete
        ])

        # Create LLM prompt
        prompt = f"""You are a medical AI assistant helping match patients to appropriate clinics.

PATIENT PROFILE:
- Name: {profile.get('full_name', 'Unknown')}
- Date of Birth: {profile.get('date_of_birth', 'N/A')}

HEALTH DATA SUMMARY:
{health_summary_text}

CHAT CONVERSATION:
{chat_text}

AVAILABLE CLINICS:
{clinics_text}

Based on the patient's health concerns from the chat conversation and their health data, recommend the top 3-5 most appropriate clinics from the list above.

For each recommended clinic, provide:
1. Clinic name
2. Relevance score (1-100)
3. Brief reasoning (1-2 sentences) explaining why this clinic matches the patient's needs

Return your response in JSON format:
{{
  "recommendations": [
    {{
      "clinic_name": "Clinic Name",
      "score": 95,
      "reasoning": "Brief explanation"
    }}
  ]
}}"""

        # Call LLM
        llm_response = get_llm_response(
            prompt=prompt,
            system_message="You are a medical AI assistant. Respond ONLY with valid JSON.",
            temperature=0.3,
            max_tokens=1000
        )

        # Parse LLM response
        import json
        try:
            recommendations_data = json.loads(llm_response)
            recommendations = recommendations_data.get('recommendations', [])
        except:
            # Fallback if LLM doesn't return valid JSON
            recommendations = []

        # Match recommendations to actual clinic objects
        recommended_clinics = []
        for rec in recommendations:
            clinic_name = rec.get('clinic_name', '')
            matching_clinic = next(
                (c for c in cabinete if c.get('nume', '').lower() == clinic_name.lower()),
                None
            )
            if matching_clinic:
                recommended_clinics.append({
                    **matching_clinic,
                    'recommendation_score': rec.get('score', 50),
                    'recommendation_reasoning': rec.get('reasoning', '')
                })

        # If no matches, return all clinics sorted by category
        if not recommended_clinics:
            recommended_clinics = cabinete

        return {
            "success": True,
            "profile": {
                "full_name": profile.get('full_name', 'Patient'),
                "email": profile.get('email', 'patient@example.com'),
                "phone": profile.get('phone', '+40 XXX XXX XXX'),
                "date_of_birth": profile.get('date_of_birth', 'N/A')
            },
            "recommended_clinics": recommended_clinics,
            "total_clinics": len(cabinete)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to recommend clinic: {str(e)}"
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


def _format_health_summary_for_email(summary: dict) -> str:
    """Helper function to format health summary as HTML for email"""
    profile = summary.get("profile", {})

    html_parts = []

    # CSS Styles
    html_parts.append("""
<style>
    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
    .profile-box { background-color: #f0f8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
    .profile-box h3 { margin-top: 0; color: #2c3e50; }
    .profile-info { margin: 5px 0; }
    .section { margin-bottom: 30px; }
    .section h3 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; background-color: white; }
    th { background-color: #3498db; color: white; padding: 12px; text-align: left; font-weight: bold; }
    td { padding: 10px; border-bottom: 1px solid #ddd; }
    tr:hover { background-color: #f5f5f5; }
    .alert { background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0; }
    .critical { background-color: #f8d7da; border-left-color: #dc3545; }
</style>
""")

    # Profile section
    html_parts.append(f"""
<div class="profile-box">
    <h3>📋 PATIENT PROFILE</h3>
    <div class="profile-info"><strong>Name:</strong> {profile.get('full_name', 'N/A')}</div>
    <div class="profile-info"><strong>Date of Birth:</strong> {profile.get('date_of_birth', 'N/A')}</div>
    <div class="profile-info"><strong>Phone:</strong> {profile.get('phone', 'N/A')}</div>
</div>
""")

    # Vital signs table
    vitale = summary.get("vitale", [])
    if vitale:
        html_parts.append('<div class="section"><h3>💓 RECENT VITAL SIGNS</h3>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Record</th><th>Blood Pressure</th><th>Pulse (bpm)</th><th>Oxygen (%)</th><th>Temperature (°C)</th></tr>')
        for idx, item in enumerate(vitale[:5], 1):
            details = item.get("details", {})
            if isinstance(details, dict):
                html_parts.append(f"""
                <tr>
                    <td>#{idx}</td>
                    <td>{details.get('tensiune', 'N/A')}</td>
                    <td>{details.get('puls', 'N/A')}</td>
                    <td>{details.get('oxigenare', 'N/A')}</td>
                    <td>{details.get('temperatura', 'N/A')}</td>
                </tr>
                """)
        html_parts.append('</table></div>')

    # Sleep patterns table
    somn = summary.get("somn", [])
    if somn:
        html_parts.append('<div class="section"><h3>😴 SLEEP PATTERNS</h3>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Record</th><th>Sleep Hours</th><th>Quality</th><th>Night Wakings</th></tr>')
        for idx, item in enumerate(somn[:5], 1):
            details = item.get("details", {})
            if isinstance(details, dict):
                html_parts.append(f"""
                <tr>
                    <td>#{idx}</td>
                    <td>{details.get('ore_somn', 'N/A')}</td>
                    <td>{details.get('calitate', 'N/A')}</td>
                    <td>{details.get('treziri', 'N/A')}</td>
                </tr>
                """)
        html_parts.append('</table></div>')

    # Physical activity table
    sport = summary.get("sport", [])
    if sport:
        html_parts.append('<div class="section"><h3>🏃 PHYSICAL ACTIVITY</h3>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Record</th><th>Type</th><th>Duration (min)</th><th>Intensity</th><th>Calories</th></tr>')
        for idx, item in enumerate(sport[:5], 1):
            details = item.get("details", {})
            if isinstance(details, dict):
                html_parts.append(f"""
                <tr>
                    <td>#{idx}</td>
                    <td>{details.get('tip', 'N/A')}</td>
                    <td>{details.get('durata_minute', 'N/A')}</td>
                    <td>{details.get('intensitate', 'N/A')}</td>
                    <td>{details.get('calorii', 'N/A')}</td>
                </tr>
                """)
        html_parts.append('</table></div>')

    # Nutrition table
    consum = summary.get("consum", [])
    if consum:
        html_parts.append('<div class="section"><h3>🍽️ NUTRITION</h3>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Record</th><th>Meals</th><th>Liquids (ml)</th><th>Calories</th></tr>')
        for idx, item in enumerate(consum[:5], 1):
            details = item.get("details", {})
            if isinstance(details, dict):
                html_parts.append(f"""
                <tr>
                    <td>#{idx}</td>
                    <td>{details.get('mese', 'N/A')}</td>
                    <td>{details.get('lichide_ml', 'N/A')}</td>
                    <td>{details.get('calorii', 'N/A')}</td>
                </tr>
                """)
        html_parts.append('</table></div>')

    # Medication table
    medicamente = summary.get("medicamente", [])
    if medicamente:
        html_parts.append('<div class="section"><h3>💊 MEDICATION</h3>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Record</th><th>Details</th></tr>')
        for idx, item in enumerate(medicamente[:5], 1):
            details = item.get("details", {})
            if isinstance(details, dict):
                details_str = ", ".join([f"{k}: {v}" for k, v in details.items()])
                html_parts.append(f"""
                <tr>
                    <td>#{idx}</td>
                    <td>{details_str}</td>
                </tr>
                """)
        html_parts.append('</table></div>')
    else:
        html_parts.append('<div class="section"><h3>💊 MEDICATION</h3><p>No medication records.</p></div>')

    return "\n".join(html_parts)


@app.post("/schedule_appointment", response_model=ScheduleAppointmentResponse)
async def schedule_appointment(request: ScheduleAppointmentRequest):
    """
    Schedule an appointment at the most appropriate clinic based on user's health data.

    This endpoint:
    1. Analyzes user's health concern and data
    2. Selects the best matching clinic from database
    3. Generates appointment request email
    4. Prints email to console (mock sending)
    5. Returns confirmation with clinic details

    Args:
        request: ScheduleAppointmentRequest containing:
            - user_id: UUID of the user
            - question: User's health question
            - generated_feedback: AI health analysis
            - summary: Complete health summary

    Returns:
        ScheduleAppointmentResponse with selected clinic and confirmation

    Example:
        POST /schedule_appointment
        {
            "user_id": "...",
            "question": "Why am I always tired?",
            "generated_feedback": "...",
            "summary": {...}
        }
    """
    try:
        # Step 1: Get all available clinics
        clinics = supabase_service.get_all_cabinete()

        if not clinics:
            raise HTTPException(
                status_code=404,
                detail="No clinics available in the system"
            )

        # Step 2: Format clinics list for LLM
        clinics_list = []
        for idx, clinic in enumerate(clinics, 1):
            clinics_list.append(
                f"{idx}. {clinic.get('name', 'Unknown')} - Category: {clinic.get('category', 'General')} "
                f"(ID: {clinic.get('id', 'N/A')})"
            )
        clinics_text = "\n".join(clinics_list)

        # Step 3: Use LLM to select best clinic
        system_message = """You are a medical triage AI assistant that matches patients to the most appropriate medical clinic.
Analyze the patient's question, health analysis, and health data to determine which clinic specialty would be most suitable.
Return ONLY the clinic ID from the provided list. Do not include any explanation, just the ID."""

        selection_prompt = f"""Patient Question: {request.question}

AI Health Analysis: {request.generated_feedback}

Patient Health Summary:
{_format_health_summary_for_email(request.summary)}

Available Clinics:
{clinics_text}

Based on the patient's symptoms, health data, and the AI analysis, which clinic is the best match?
Return ONLY the clinic ID."""

        llm_selection = get_llm_response(
            prompt=selection_prompt,
            system_message=system_message,
            temperature=0.3,
            max_tokens=50
        )

        # Step 4: Find selected clinic
        selected_clinic = None
        clinic_id = llm_selection.strip()

        for clinic in clinics:
            if str(clinic.get('id')) == clinic_id or clinic.get('name') in llm_selection:
                selected_clinic = clinic
                break

        # If LLM didn't return exact match, use first clinic as fallback
        if not selected_clinic:
            selected_clinic = clinics[0]

        # Step 5: Extract patient contact info
        profile = request.summary.get("profile", {})
        patient_name = profile.get("full_name", "Unknown Patient")
        patient_email = profile.get("email", "N/A")
        patient_phone = profile.get("phone", "N/A")
        patient_dob = profile.get("date_of_birth", "N/A")

        clinic_name = selected_clinic.get("name", "Medical Clinic")
        clinic_email = selected_clinic.get("email", "clinic@example.com")

        # Step 6: Format health summary for email
        formatted_summary = _format_health_summary_for_email(request.summary)

        # Step 7: Build HTML email content
        email_content = f"""==================== APPOINTMENT REQUEST EMAIL ====================
To: {clinic_email}
From: medflow@gmail.com
Subject: Urgent Appointment Request - Patient Health Consultation
Content-Type: text/html; charset=utf-8

<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Appointment Request - MedFlowAI</title>
    {formatted_summary.split('</style>')[0]}</style>
</head>
<body>
    <div style="max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f9f9f9;">

        <!-- Header -->
        <div style="background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
            <h1 style="margin: 0;">🏥 MedFlowAI - Appointment Request</h1>
            <p style="margin: 5px 0 0 0; font-size: 14px;">Priority Medical Consultation Required</p>
        </div>

        <!-- Greeting -->
        <div style="background-color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0;">Dear {clinic_name},</h2>
            <p>MedFlowAI is forwarding a <strong>priority appointment request</strong> for a patient requiring professional medical consultation based on AI health analysis.</p>
        </div>

        <!-- Patient Contact Information -->
        <div style="background-color: #e8f4f8; padding: 20px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #3498db;">
            <h3 style="color: #2c3e50; margin-top: 0;">📞 PATIENT CONTACT INFORMATION</h3>
            <table style="width: 100%; border: none;">
                <tr><td style="border: none; padding: 5px;"><strong>Name:</strong></td><td style="border: none; padding: 5px;">{patient_name}</td></tr>
                <tr><td style="border: none; padding: 5px;"><strong>Email:</strong></td><td style="border: none; padding: 5px;"><a href="mailto:{patient_email}">{patient_email}</a></td></tr>
                <tr><td style="border: none; padding: 5px;"><strong>Phone:</strong></td><td style="border: none; padding: 5px;"><a href="tel:{patient_phone}">{patient_phone}</a></td></tr>
                <tr><td style="border: none; padding: 5px;"><strong>Date of Birth:</strong></td><td style="border: none; padding: 5px;">{patient_dob}</td></tr>
            </table>
        </div>

        <!-- Patient's Health Concern -->
        <div style="background-color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
            <h3 style="color: #2c3e50; margin-top: 0;">❓ PATIENT'S HEALTH CONCERN</h3>
            <p style="font-size: 16px; font-style: italic; color: #555; background-color: #f8f9fa; padding: 15px; border-radius: 5px;">"{request.question}"</p>
        </div>

        <!-- AI Health Analysis -->
        <div style="background-color: #fff3cd; padding: 20px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #ffc107;">
            <h3 style="color: #2c3e50; margin-top: 0;">🤖 AI HEALTH ANALYSIS</h3>
            <p style="line-height: 1.8;">{request.generated_feedback}</p>
        </div>

        <!-- Patient Health Summary -->
        <div style="background-color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px;">
            <h2 style="color: #2c3e50; margin-top: 0; border-bottom: 3px solid #3498db; padding-bottom: 10px;">📊 PATIENT HEALTH SUMMARY</h2>
            {formatted_summary.split('</style>')[1] if '</style>' in formatted_summary else formatted_summary}
        </div>

        <!-- Request Section -->
        <div style="background-color: #d4edda; padding: 20px; border-radius: 5px; margin-bottom: 20px; border-left: 4px solid #28a745;">
            <h3 style="color: #155724; margin-top: 0;">✅ REQUEST</h3>
            <p>This patient requires <strong>professional medical evaluation</strong> based on the symptoms and health patterns identified. Please contact the patient directly to schedule an appointment at your earliest convenience.</p>

            <div style="background-color: white; padding: 15px; border-radius: 5px; margin-top: 15px;">
                <h4 style="margin-top: 0; color: #2c3e50;">Patient Contact:</h4>
                <ul style="list-style: none; padding: 0;">
                    <li>📧 Email: <a href="mailto:{patient_email}">{patient_email}</a></li>
                    <li>📱 Phone: <a href="tel:{patient_phone}">{patient_phone}</a></li>
                </ul>
            </div>
        </div>

        <!-- Footer -->
        <div style="background-color: #2c3e50; color: white; padding: 20px; border-radius: 5px; text-align: center;">
            <p style="margin: 0; font-size: 14px;">This referral is sent via <strong>MedFlowAI</strong> health monitoring system to ensure timely medical intervention.</p>
            <p style="margin: 10px 0 0 0; font-size: 12px;">Best regards,<br><strong>MedFlowAI Team</strong><br>📧 medflow@gmail.com</p>
        </div>

    </div>
</body>
</html>
==================================================================="""

        # Step 8: Print email to console (mock sending)
        print("\n" + email_content + "\n")

        # Step 9: Return response
        return ScheduleAppointmentResponse(
            success=True,
            selected_clinic=selected_clinic,
            message=f"Appointment request prepared for {clinic_name}. Email content displayed in console."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule appointment: {str(e)}"
        )

