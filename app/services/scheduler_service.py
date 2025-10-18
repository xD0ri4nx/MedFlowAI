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
                "feedback": "No data recorded for this day."
            }
        
        # Create prompt for LLM
        user_name = summary.get("profile", {}).get("full_name", "User")
        
        prompt = f"""Analyze the daily medical data for {user_name} from {target_date}:

PATIENT PROFILE:
- Name: {user_name}
- Date of birth: {summary.get("profile", {}).get("date_of_birth", "N/A")}

DAILY DATA ({target_date}):

NUTRITION (meals and liquids):
{_format_data_section(summary.get("consum", []))}

SLEEP:
{_format_data_section(summary.get("somn", []))}

VITALS (blood pressure, pulse, oxygen):
{_format_data_section(summary.get("vitale", []))}

EXERCISE (physical activity):
{_format_data_section(summary.get("sport", []))}

---

Provide VERY SHORT feedback (max 2-3 sentences!):
- Quick overall assessment (1 sentence)
- 2-3 main recommendations (very concise)

IMPORTANT: Format response using Markdown:
- Use **bold** for key words
- Use bullet points (•) for recommendations
- DO NOT use section titles
- Keep VERY SHORT - maximum 3-4 lines total!

Respond in English, very concise."""

        score_prompt = f"""Based on the medical data above for {user_name}, evaluate overall health status with a score between 0-100:

BE CRITICAL AND REALISTIC! DO NOT give high scores if data is incomplete or not optimal.

- 0-20: Critical (most data missing or very abnormal values)
- 21-40: Concerning (incomplete data, multiple problems)
- 41-60: Medium (partial data, suboptimal values, needs improvement)
- 61-75: Acceptable (relatively complete data, but with gaps)
- 76-85: Good (complete data, most values in normal ranges)
- 86-95: Very good (complete data, optimal values, healthy lifestyle)
- 96-100: Excellent (perfect data, all categories with ideal values)

STRICT CRITERIA:
- Missing entire category (nutrition/sleep/vitals/exercise)? Max score 60
- Sleep under 6h or over 10h? Penalty -15 points
- Abnormal vitals (BP >140/90 or <100/60, pulse >100 or <50)? Penalty -20 points
- No physical activity? Penalty -15 points
- Hydration under 1.5L? Penalty -10 points
- Less than 2 meals per day? Penalty -10 points

Start with 50 base points and adjust up/down based on data quality.

Respond ONLY with the number (e.g., 45). Nothing else!"""

        system_message = """You are a medical AI assistant specialized in health data analysis. 
Respond in English EXTREMELY CONCISE - maximum 2-3 sentences total.
Use Markdown for formatting (bold and bullet points), no titles."""

        # Get LLM feedback
        feedback = get_llm_response(
            prompt=prompt,
            system_message=system_message,
            temperature=0.7,
            max_tokens=800
        )
        
        # Get health score
        health_score = get_llm_response(
            prompt=score_prompt,
            system_message="You are a medical evaluator. Respond ONLY with a number between 0-100.",
            temperature=0.3,
            max_tokens=10
        )
        
        # Extract numeric score
        try:
            score = int(''.join(filter(str.isdigit, health_score)))
            score = max(0, min(100, score))  # Clamp between 0-100
        except:
            score = 50  # Default fallback
        
        # Extract numeric score
        try:
            score = int(''.join(filter(str.isdigit, health_score)))
            score = max(0, min(100, score))  # Clamp between 0-100
        except:
            score = 50  # Default fallback
        
        logger.info(f"Generated alert for user {user_id} with health score: {score}")
        
        return {
            "user_id": user_id,
            "date": str(target_date),
            "summary": summary,
            "feedback": feedback,
            "health_score": score,
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
