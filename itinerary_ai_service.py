import os
import google.generativeai as genai
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from db_connection import fetch_all, fetch_one

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class FreeTimeSlot:
    def __init__(self, start_time: str, end_time: str, duration_minutes: int, context: str = ""):
        self.start_time = start_time
        self.end_time = end_time
        self.duration_minutes = duration_minutes
        self.context = context

class ActivitySuggestion:
    def __init__(self, activity_id: int, title: str, location: str, duration_minutes: int, 
                 price: float, rating: float, category: str, description: str = ""):
        self.activity_id = activity_id
        self.title = title
        self.location = location
        self.duration_minutes = duration_minutes
        self.price = price
        self.rating = rating
        self.category = category
        self.description = description

async def get_user_bookings(user_id: int) -> List[Dict[str, Any]]:
    """Fetch all active bookings for a user"""
    try:
        # Query to get all active bookings (hotels, flights, activities)
        sql = """
        SELECT 
            'hotel' as booking_type,
            id,
            hotel_name as title,
            location,
            check_in_date as start_date,
            check_out_date as end_date,
            check_in_time as start_time,
            check_out_time as end_time,
            booking_id,
            NULL as duration_minutes
        FROM hotel_bookings 
        WHERE user_id = %s AND status = 'active'
        
        UNION ALL
        
        SELECT 
            'flight' as booking_type,
            id,
            CONCAT(departure_city, ' to ', arrival_city) as title,
            CONCAT(departure_city, ', ', arrival_city) as location,
            departure_date as start_date,
            arrival_date as end_date,
            departure_time as start_time,
            arrival_time as end_time,
            booking_id,
            flight_duration_minutes as duration_minutes
        FROM flight_bookings 
        WHERE user_id = %s AND status = 'active'
        
        UNION ALL
        
        SELECT 
            'activity' as booking_type,
            id,
            activity_name as title,
            location,
            activity_date as start_date,
            activity_date as end_date,
            start_time,
            end_time,
            booking_id,
            duration_minutes
        FROM activity_bookings 
        WHERE user_id = %s AND status = 'active'
        
        ORDER BY start_date, start_time
        """
        
        bookings = await fetch_all(sql, (user_id, user_id, user_id))
        return bookings
    except Exception as e:
        print(f"Error fetching user bookings: {str(e)}")
        return []

def analyze_free_time_slots(bookings: List[Dict[str, Any]]) -> List[FreeTimeSlot]:
    """Analyze bookings to find free time slots"""
    free_slots = []
    
    if not bookings:
        return free_slots
    
    # Sort bookings by date and time
    sorted_bookings = sorted(bookings, key=lambda x: (x['start_date'], x['start_time']))
    
    # Get the date range of the trip
    start_date = min(booking['start_date'] for booking in sorted_bookings)
    end_date = max(booking['end_date'] for booking in sorted_bookings)
    
    # Analyze each day
    current_date = start_date
    while current_date <= end_date:
        day_bookings = [b for b in sorted_bookings if b['start_date'] <= current_date <= b['end_date']]
        
        if not day_bookings:
            # Free day
            free_slots.append(FreeTimeSlot(
                start_time="09:00",
                end_time="18:00",
                duration_minutes=540,
                context="Free day - no bookings scheduled"
            ))
        else:
            # Find gaps between bookings
            day_slots = find_daily_free_slots(day_bookings, current_date)
            free_slots.extend(day_slots)
        
        current_date += timedelta(days=1)
    
    return free_slots

def find_daily_free_slots(day_bookings: List[Dict[str, Any]], date) -> List[FreeTimeSlot]:
    """Find free time slots within a specific day"""
    free_slots = []
    
    # Sort by start time
    day_bookings.sort(key=lambda x: x['start_time'])
    
    # Check for morning free time (before first booking)
    if day_bookings:
        first_booking = day_bookings[0]
        if first_booking['start_time'] > "09:00":
            duration = time_to_minutes(first_booking['start_time']) - time_to_minutes("09:00")
            if duration >= 60:  # At least 1 hour free
                free_slots.append(FreeTimeSlot(
                    start_time="09:00",
                    end_time=first_booking['start_time'],
                    duration_minutes=duration,
                    context="Morning free time"
                ))
    
    # Check for gaps between bookings
    for i in range(len(day_bookings) - 1):
        current_end = day_bookings[i]['end_time']
        next_start = day_bookings[i + 1]['start_time']
        
        if current_end < next_start:
            duration = time_to_minutes(next_start) - time_to_minutes(current_end)
            if duration >= 60:  # At least 1 hour free
                free_slots.append(FreeTimeSlot(
                    start_time=current_end,
                    end_time=next_start,
                    duration_minutes=duration,
                    context="Gap between bookings"
                ))
    
    # Check for evening free time (after last booking)
    if day_bookings:
        last_booking = day_bookings[-1]
        if last_booking['end_time'] < "22:00":
            duration = time_to_minutes("22:00") - time_to_minutes(last_booking['end_time'])
            if duration >= 60:  # At least 1 hour free
                free_slots.append(FreeTimeSlot(
                    start_time=last_booking['end_time'],
                    end_time="22:00",
                    duration_minutes=duration,
                    context="Evening free time"
                ))
    
    return free_slots

def time_to_minutes(time_str: str) -> int:
    """Convert time string (HH:MM) to minutes since midnight"""
    try:
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        return time_obj.hour * 60 + time_obj.minute
    except:
        return 0

def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to time string (HH:MM)"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

async def get_activity_suggestions(category: str, location: str = None, 
                                 duration_minutes: int = None, 
                                 max_price: float = None) -> List[ActivitySuggestion]:
    """Get activity suggestions based on category and filters"""
    try:
        # Build the query based on filters
        where_conditions = ["category = %s", "status = 'active'"]
        params = [category]
        
        if location:
            where_conditions.append("location LIKE %s")
            params.append(f"%{location}%")
        
        if duration_minutes:
            where_conditions.append("duration_minutes <= %s")
            params.append(duration_minutes)
        
        if max_price:
            where_conditions.append("price <= %s")
            params.append(max_price)
        
        where_clause = " AND ".join(where_conditions)
        
        sql = f"""
        SELECT 
            id,
            title,
            location,
            duration_minutes,
            price,
            rating,
            category,
            description
        FROM activities 
        WHERE {where_clause}
        ORDER BY rating DESC, price ASC
        LIMIT 20
        """
        
        activities = await fetch_all(sql, params)
        
        suggestions = []
        for activity in activities:
            suggestions.append(ActivitySuggestion(
                activity_id=activity['id'],
                title=activity['title'],
                location=activity['location'],
                duration_minutes=activity['duration_minutes'],
                price=activity['price'],
                rating=activity['rating'],
                category=activity['category'],
                description=activity['description']
            ))
        
        return suggestions
    except Exception as e:
        print(f"Error fetching activity suggestions: {str(e)}")
        return []

def generate_contextual_message(free_slots: List[FreeTimeSlot]) -> str:
    """Generate AI-powered contextual message about free time"""
    if not free_slots:
        return "No free time slots found in your current itinerary."
    
    # Find the largest free slot
    largest_slot = max(free_slots, key=lambda x: x.duration_minutes)
    
    # Use AI to generate a contextual message
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        You are a travel assistant. The user has free time from {largest_slot.start_time} to {largest_slot.end_time} 
        (duration: {largest_slot.duration_minutes} minutes) in their travel itinerary.
        
        Generate a friendly, engaging message that:
        1. Acknowledges their free time
        2. Suggests they can book activities
        3. Asks what type of experience they're in the mood for
        4. Keep it concise and exciting (2-3 sentences max)
        
        The context is: {largest_slot.context}
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Fallback message if AI fails
        return f"You've got some free time between {largest_slot.start_time} and {largest_slot.end_time}. What kind of experience are you in the mood for?"

async def analyze_user_itinerary(user_id: int) -> Dict[str, Any]:
    """Main function to analyze user itinerary and return free time slots"""
    try:
        # Get user bookings
        bookings = await get_user_bookings(user_id)
        
        # Analyze free time slots
        free_slots = analyze_free_time_slots(bookings)
        
        # Generate contextual message
        contextual_message = generate_contextual_message(free_slots)
        
        # Format response
        response = {
            "user_id": user_id,
            "total_bookings": len(bookings),
            "free_time_slots": [
                {
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "duration_minutes": slot.duration_minutes,
                    "context": slot.context
                }
                for slot in free_slots
            ],
            "contextual_message": contextual_message,
            "bookings": bookings
        }
        
        return response
    except Exception as e:
        return {
            "error": f"Failed to analyze itinerary: {str(e)}",
            "user_id": user_id,
            "free_time_slots": [],
            "contextual_message": "Unable to analyze your itinerary at this time."
        }
