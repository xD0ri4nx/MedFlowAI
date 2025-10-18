"""Scheduler Service for periodic health alert generation"""
from datetime import date
from typing import List
import asyncio
from app.services.supabase_service import supabase_service
from app.services.llm_service import get_llm_response
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _format_data_section(data_list: List) -> str:
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


async def generate_alert_for_user(user_id: str, target_date: date = None) -> dict:
    """
    Generate health alert for a single user.
    
    Args:
        user_id: UUID of the user
        target_date: Date to analyze (default: today)
        
    Returns:
        Dictionary with alert data
    """
    try:
        if target_date is None:
            target_date = date.today()
        
        # Get daily summary
        summary = supabase_service.get_daily_summary(user_id, target_date)
        
        # Check if user exists
        if not summary.get("profile"):
            logger.warning(f"User {user_id} not found")
            return {
                "user_id": user_id,
                "success": False,
                "error": "User not found"
            }
        
        # Check if there's any data
        if summary.get("total_records", 0) == 0:
            logger.info(f"No data for user {user_id} on {target_date}")
            return {
                "user_id": user_id,
                "date": str(target_date),
                "success": True,
                "feedback": "Nu există date înregistrate pentru această zi."
            }
        
        # Create prompt for LLM
        user_name = summary.get("profile", {}).get("full_name", "Utilizator")
        
        prompt = f"""Analizează datele medicale zilnice pentru {user_name} din data de {target_date}:

PROFIL PACIENT:
- Nume: {user_name}
- Data nașterii: {summary.get("profile", {}).get("date_of_birth", "N/A")}

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

Oferă o analiză scurtă și concisă cu:
1. Evaluare generală
2. Alerte (dacă există probleme)
3. 2-3 recomandări principale

Răspunde în limba română, profesional dar accesibil."""

        system_message = """Ești un asistent medical AI specializat în analiza datelor de sănătate. 
Analizezi date zilnice și oferi feedback constructiv și recomandări personalizate.
Răspunzi în limba română, concis in (MAXIMUM 3 PROPOZITII!!!!!!!!!!) și la obiect."""

        # Get LLM feedback
        feedback = get_llm_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=800
        )
        
        logger.info(f"Generated alert for user {user_id}")
        
        return {
            "user_id": user_id,
            "date": str(target_date),
            "summary": summary,
            "feedback": feedback,
            "success": True
        }
    
    except Exception as e:
        logger.error(f"Error generating alert for user {user_id}: {str(e)}")
        return {
            "user_id": user_id,
            "success": False,
            "error": str(e)
        }


async def generate_alerts_for_all_users(target_date: date = None) -> List[dict]:
    """
    Generate health alerts for all users in the system.
    
    This function is designed to be run periodically (e.g., every X hours)
    to analyze health data and generate personalized feedback.
    
    Args:
        target_date: Date to analyze (default: today)
        
    Returns:
        List of alert results for all users
    """
    try:
        if target_date is None:
            target_date = date.today()
        
        logger.info(f"Starting alert generation for all users on {target_date}")
        
        # Get all user profiles
        profiles = supabase_service.get_all_profiles()
        logger.info(f"Found {len(profiles)} users")
        
        # Generate alerts for each user
        results = []
        for profile in profiles:
            user_id = profile.get("id")
            if user_id:
                result = await generate_alert_for_user(user_id, target_date)
                results.append(result)
                
                # Small delay to avoid rate limiting
                await asyncio.sleep(0.5)
        
        successful = sum(1 for r in results if r.get("success"))
        logger.info(f"Alert generation completed: {successful}/{len(results)} successful")
        
        return results
    
    except Exception as e:
        logger.error(f"Error in batch alert generation: {str(e)}")
        raise


async def scheduled_alert_task():
    """
    Scheduled task to run periodically.
    
    This is the main task that should be scheduled to run every X hours
    using a task scheduler (cron, APScheduler, etc.)
    """
    logger.info("=== Starting scheduled alert generation task ===")
    try:
        results = await generate_alerts_for_all_users()
        logger.info(f"Task completed. Generated {len(results)} alerts")
        return results
    except Exception as e:
        logger.error(f"Scheduled task failed: {str(e)}")
        raise
    finally:
        logger.info("=== Scheduled alert generation task finished ===")


# For manual testing
async def test_scheduler():
    """Test function to run the scheduler manually"""
    print("Testing scheduler service...")
    results = await scheduled_alert_task()
    print(f"\nResults: {len(results)} alerts generated")
    for result in results:
        print(f"\nUser: {result.get('user_id')}")
        print(f"Success: {result.get('success')}")
        if result.get('feedback'):
            print(f"Feedback preview: {result.get('feedback')[:100]}...")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_scheduler())
