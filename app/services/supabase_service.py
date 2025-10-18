"""Supabase Service for database operations"""
from typing import List, Dict, Optional, Any
from datetime import date, datetime, timedelta
from supabase import create_client, Client
from config import settings
import json

# Initialize Supabase client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_API_KEY)


class SupabaseService:
    """Service class for Supabase database operations"""

    def __init__(self):
        self.client = supabase

    # ==================== PROFILES ====================
    
    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID.
        
        Args:
            user_id: UUID of the user
            
        Returns:
            Profile data or None if not found
        """
        try:
            response = self.client.table("profiles").select("*").eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Error fetching profile: {str(e)}")

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """
        Get all user profiles.
        
        Returns:
            List of all profiles
        """
        try:
            response = self.client.table("profiles").select("*").execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching profiles: {str(e)}")

    # ==================== GENERAL DATA ====================
    
    def select_general(
        self, 
        user_id: str, 
        target_date: Optional[date] = None,
        type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Select general health data for a user on a specific date.
        
        Args:
            user_id: UUID of the user
            target_date: Date to filter by (default: today)
            type_filter: Optional filter by type (consum, somn, vitale, sport)
            
        Returns:
            List of general health records
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            query = self.client.table("general").select("*").eq("user_id", user_id)
            
            if type_filter:
                query = query.eq("type", type_filter)
            
            response = query.execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching general data: {str(e)}")

    def get_general_by_date_range(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        type_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get general data for a date range.
        
        Args:
            user_id: UUID of the user
            start_date: Start date
            end_date: End date
            type_filter: Optional filter by type
            
        Returns:
            List of general health records
        """
        try:
            query = self.client.table("general").select("*").eq("user_id", user_id).gte("data", str(start_date)).lte("data", str(end_date))
            
            if type_filter:
                query = query.eq("type", type_filter)
            
            response = query.order("data", desc=True).execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching general data by range: {str(e)}")

    def insert_general(
        self,
        user_id: str,
        data: date,
        details: Dict[str, Any],
        type_: str
    ) -> Dict[str, Any]:
        """
        Insert new general health data.
        
        Args:
            user_id: UUID of the user
            data: Date of the record
            details: JSON data with health details
            type_: Type of data (consum, somn, vitale, sport)
            
        Returns:
            Inserted record
        """
        try:
            record = {
                "user_id": user_id,
                "data": str(data),
                "details": json.dumps(details) if isinstance(details, dict) else details,
                "type": type_
            }
            response = self.client.table("general").insert(record).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            raise Exception(f"Error inserting general data: {str(e)}")

    # ==================== CABINETE ====================
    
    def get_all_cabinete(self) -> List[Dict[str, Any]]:
        """
        Get all medical offices/clinics.
        
        Returns:
            List of all cabinete
        """
        try:
            response = self.client.table("cabinete").select("*").execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching cabinete: {str(e)}")

    def get_cabinete_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get medical offices by category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of matching cabinete
        """
        try:
            response = self.client.table("cabinete").select("*").ilike("category", f"%{category}%").execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching cabinete by category: {str(e)}")

    def get_cabinet(self, cabinet_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific medical office by ID.
        
        Args:
            cabinet_id: UUID of the cabinet
            
        Returns:
            Cabinet data or None
        """
        try:
            response = self.client.table("cabinete").select("*").eq("id", cabinet_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            raise Exception(f"Error fetching cabinet: {str(e)}")

    # ==================== PROGRAMARI ====================
    
    def get_user_programari(
        self, 
        user_id: str, 
        active_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get user's appointments.
        
        Args:
            user_id: UUID of the user
            active_only: If True, return only active appointments
            
        Returns:
            List of appointments with cabinet details
        """
        try:
            query = self.client.table("programari").select("*, cabinete(*)").eq("user_id", user_id)
            
            if active_only:
                query = query.eq("active", True)
            
            response = query.order("data", desc=False).execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching programari: {str(e)}")

    def create_programare(
        self,
        user_id: str,
        cabinet_id: str,
        data: date,
        active: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new appointment.
        
        Args:
            user_id: UUID of the user
            cabinet_id: UUID of the cabinet
            data: Date of the appointment
            active: Whether the appointment is active
            
        Returns:
            Created appointment record
        """
        try:
            record = {
                "user_id": user_id,
                "cabinet_id": cabinet_id,
                "data": str(data),
                "active": active
            }
            response = self.client.table("programari").insert(record).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            raise Exception(f"Error creating programare: {str(e)}")

    def update_programare_status(
        self,
        programare_id: str,
        active: bool
    ) -> Dict[str, Any]:
        """
        Update appointment status (active/inactive).
        
        Args:
            programare_id: UUID of the appointment
            active: New active status
            
        Returns:
            Updated appointment record
        """
        try:
            response = self.client.table("programari").update({"active": active}).eq("id", programare_id).execute()
            return response.data[0] if response.data else {}
        except Exception as e:
            raise Exception(f"Error updating programare: {str(e)}")

    # ==================== DATA SUMMARY & ANALYSIS ====================
    
    def get_daily_summary(
        self, 
        user_id: str, 
        target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get a comprehensive daily summary of all health data for a user.
        
        Args:
            user_id: UUID of the user
            target_date: Date to summarize (default: today)
            
        Returns:
            Dictionary with all health data organized by type
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            # Get all general data for the date
            general_data = self.select_general(user_id, target_date)
            
            # Get user profile
            profile = self.get_profile(user_id)
            
            # Organize data by type
            summary = {
                "user_id": user_id,
                "profile": profile,
                "date": str(target_date),
                "consum": [],
                "somn": [],
                "vitale": [],
                "sport": [],
                "medicamente": [],
                "total_records": len(general_data)
            }
            
            for record in general_data:
                record_type = record.get("type")
                if record_type in summary:
                    # Parse details if it's a JSON string
                    details = record.get("details", "{}")
                    if isinstance(details, str):
                        try:
                            details = json.loads(details)
                        except:
                            pass
                    
                    summary[record_type].append({
                        "id": record.get("id"),
                        "details": details,
                        "created_at": record.get("created_at")
                    })
            


            return summary
        except Exception as e:
            raise Exception(f"Error generating daily summary: {str(e)}")

    def get_weekly_summary(
        self,
        user_id: str,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get a weekly summary (last 7 days) of health data.
        
        Args:
            user_id: UUID of the user
            end_date: End date (default: today)
            
        Returns:
            Dictionary with weekly health data
        """
        try:
            if end_date is None:
                end_date = date.today()
            
            start_date = end_date - timedelta(days=7)
            
            # Get all data for the week
            general_data = self.get_general_by_date_range(user_id, start_date, end_date)
            
            # Get user profile
            profile = self.get_profile(user_id)
            
            summary = {
                "user_id": user_id,
                "profile": profile,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "consum": [],
                "somn": [],
                "vitale": [],
                "sport": [],
                "medicamente": [],
                "total_records": len(general_data)
            }
            
            for record in general_data:
                record_type = record.get("type")
                if record_type in summary:
                    details = record.get("details", "{}")
                    if isinstance(details, str):
                        try:
                            details = json.loads(details)
                        except:
                            pass
                    
                    summary[record_type].append({
                        "date": record.get("data"),
                        "details": details,
                        "created_at": record.get("created_at")
                    })
            
            return summary
        except Exception as e:
            raise Exception(f"Error generating weekly summary: {str(e)}")


# Create singleton instance
supabase_service = SupabaseService()
