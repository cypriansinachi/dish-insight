import os
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from db_connection import fetch_all, fetch_one

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class ActivitySuggestion:
    def __init__(self, activity_id: int, title: str, location: str, duration_minutes: int, 
                 price: float, rating: float, category: str, description: str = "",
                 image_url: str = "", provider: str = "", availability: str = ""):
        self.activity_id = activity_id
        self.title = title
        self.location = location
        self.duration_minutes = duration_minutes
        self.price = price
        self.rating = rating
        self.category = category
        self.description = description
        self.image_url = image_url
        self.provider = provider
        self.availability = availability

    def to_dict(self):
        return {
            "activity_id": self.activity_id,
            "title": self.title,
            "location": self.location,
            "duration_minutes": self.duration_minutes,
            "duration_display": f"{self.duration_minutes // 60}h {self.duration_minutes % 60}m" if self.duration_minutes >= 60 else f"{self.duration_minutes}m",
            "price": self.price,
            "price_display": f"₦{self.price:,.2f}",
            "rating": self.rating,
            "rating_display": f"{self.rating} ({int(self.rating * 50)})",  # Approximate review count
            "category": self.category,
            "description": self.description,
            "image_url": self.image_url,
            "provider": self.provider,
            "availability": self.availability
        }

async def get_activities_by_category(category: str, location: str = None, 
                                   duration_minutes: int = None, 
                                   max_price: float = None,
                                   limit: int = 20) -> List[ActivitySuggestion]:
    """Get activities filtered by category and other criteria"""
    try:
        # Map category names to database values
        category_mapping = {
            "adventurous": "adventure",
            "relax": "relaxation",
            "luxurious": "luxury",
            "cultural": "culture"
        }
        
        db_category = category_mapping.get(category.lower(), category.lower())
        
        # Build the query based on filters
        where_conditions = ["category = %s", "status = 'active'"]
        params = [db_category]
        
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
            description,
            image_url,
            provider,
            availability
        FROM activities 
        WHERE {where_clause}
        ORDER BY rating DESC, price ASC
        LIMIT %s
        """
        
        params.append(limit)
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
                description=activity['description'],
                image_url=activity.get('image_url', ''),
                provider=activity.get('provider', ''),
                availability=activity.get('availability', 'Flexible dates')
            ))
        
        return suggestions
    except Exception as e:
        print(f"Error fetching activities by category: {str(e)}")
        return []

async def get_restaurants_by_category(category: str, location: str = None, 
                                    max_price: float = None,
                                    limit: int = 20) -> List[ActivitySuggestion]:
    """Get restaurants filtered by category and other criteria"""
    try:
        # Map category to cuisine type
        cuisine_mapping = {
            "adventurous": "exotic",
            "relax": "casual",
            "luxurious": "fine_dining",
            "cultural": "traditional"
        }
        
        cuisine_type = cuisine_mapping.get(category.lower(), "general")
        
        where_conditions = ["status = 'active'"]
        params = []
        
        if cuisine_type != "general":
            where_conditions.append("cuisine_type = %s")
            params.append(cuisine_type)
        
        if location:
            where_conditions.append("location LIKE %s")
            params.append(f"%{location}%")
        
        if max_price:
            where_conditions.append("average_price <= %s")
            params.append(max_price)
        
        where_clause = " AND ".join(where_conditions)
        
        sql = f"""
        SELECT 
            id,
            restaurant_name as title,
            location,
            estimated_duration_minutes as duration_minutes,
            average_price as price,
            rating,
            'restaurant' as category,
            description,
            image_url,
            provider,
            'Flexible times' as availability
        FROM restaurants 
        WHERE {where_clause}
        ORDER BY rating DESC, average_price ASC
        LIMIT %s
        """
        
        params.append(limit)
        restaurants = await fetch_all(sql, params)
        
        suggestions = []
        for restaurant in restaurants:
            suggestions.append(ActivitySuggestion(
                activity_id=restaurant['id'],
                title=restaurant['title'],
                location=restaurant['location'],
                duration_minutes=restaurant['duration_minutes'],
                price=restaurant['price'],
                rating=restaurant['rating'],
                category=restaurant['category'],
                description=restaurant['description'],
                image_url=restaurant.get('image_url', ''),
                provider=restaurant.get('provider', ''),
                availability=restaurant['availability']
            ))
        
        return suggestions
    except Exception as e:
        print(f"Error fetching restaurants by category: {str(e)}")
        return []

async def get_nightlife_by_category(category: str, location: str = None, 
                                  max_price: float = None,
                                  limit: int = 20) -> List[ActivitySuggestion]:
    """Get nightlife venues filtered by category and other criteria"""
    try:
        # Map category to nightlife type
        nightlife_mapping = {
            "adventurous": "adventure_bar",
            "relax": "lounge",
            "luxurious": "upscale_club",
            "cultural": "cultural_venue"
        }
        
        venue_type = nightlife_mapping.get(category.lower(), "general")
        
        where_conditions = ["status = 'active'"]
        params = []
        
        if venue_type != "general":
            where_conditions.append("venue_type = %s")
            params.append(venue_type)
        
        if location:
            where_conditions.append("location LIKE %s")
            params.append(f"%{location}%")
        
        if max_price:
            where_conditions.append("cover_charge <= %s")
            params.append(max_price)
        
        where_clause = " AND ".join(where_conditions)
        
        sql = f"""
        SELECT 
            id,
            venue_name as title,
            location,
            180 as duration_minutes,  # Default 3 hours for nightlife
            cover_charge as price,
            rating,
            'nightlife' as category,
            description,
            image_url,
            provider,
            'Evening hours' as availability
        FROM nightlife_venues 
        WHERE {where_clause}
        ORDER BY rating DESC, cover_charge ASC
        LIMIT %s
        """
        
        params.append(limit)
        venues = await fetch_all(sql, params)
        
        suggestions = []
        for venue in venues:
            suggestions.append(ActivitySuggestion(
                activity_id=venue['id'],
                title=venue['title'],
                location=venue['location'],
                duration_minutes=venue['duration_minutes'],
                price=venue['price'],
                rating=venue['rating'],
                category=venue['category'],
                description=venue['description'],
                image_url=venue.get('image_url', ''),
                provider=venue.get('provider', ''),
                availability=venue['availability']
            ))
        
        return suggestions
    except Exception as e:
        print(f"Error fetching nightlife venues by category: {str(e)}")
        return []

async def get_events_by_category(category: str, location: str = None, 
                               max_price: float = None,
                               limit: int = 20) -> List[ActivitySuggestion]:
    """Get events filtered by category and other criteria"""
    try:
        # Map category to event type
        event_mapping = {
            "adventurous": "sports",
            "relax": "wellness",
            "luxurious": "exclusive",
            "cultural": "cultural"
        }
        
        event_type = event_mapping.get(category.lower(), "general")
        
        where_conditions = ["status = 'active'", "event_date >= CURDATE()"]
        params = []
        
        if event_type != "general":
            where_conditions.append("event_type = %s")
            params.append(event_type)
        
        if location:
            where_conditions.append("location LIKE %s")
            params.append(f"%{location}%")
        
        if max_price:
            where_conditions.append("ticket_price <= %s")
            params.append(max_price)
        
        where_clause = " AND ".join(where_conditions)
        
        sql = f"""
        SELECT 
            id,
            event_name as title,
            location,
            duration_minutes,
            ticket_price as price,
            rating,
            'event' as category,
            description,
            image_url,
            organizer as provider,
            CONCAT('Event on ', event_date) as availability
        FROM events 
        WHERE {where_clause}
        ORDER BY event_date ASC, rating DESC
        LIMIT %s
        """
        
        params.append(limit)
        events = await fetch_all(sql, params)
        
        suggestions = []
        for event in events:
            suggestions.append(ActivitySuggestion(
                activity_id=event['id'],
                title=event['title'],
                location=event['location'],
                duration_minutes=event['duration_minutes'],
                price=event['price'],
                rating=event['rating'],
                category=event['category'],
                description=event['description'],
                image_url=event.get('image_url', ''),
                provider=event.get('provider', ''),
                availability=event['availability']
            ))
        
        return suggestions
    except Exception as e:
        print(f"Error fetching events by category: {str(e)}")
        return []

async def get_suggestions_by_type_and_category(suggestion_type: str, category: str, 
                                             location: str = None,
                                             duration_minutes: int = None,
                                             max_price: float = None,
                                             limit: int = 20) -> Dict[str, Any]:
    """Get suggestions based on type (activities, restaurants, nightlife, events) and category"""
    try:
        suggestions = []
        
        if suggestion_type.lower() == "activities":
            suggestions = await get_activities_by_category(
                category, location, duration_minutes, max_price, limit
            )
        elif suggestion_type.lower() == "restaurants":
            suggestions = await get_restaurants_by_category(
                category, location, max_price, limit
            )
        elif suggestion_type.lower() == "nightlife":
            suggestions = await get_nightlife_by_category(
                category, location, max_price, limit
            )
        elif suggestion_type.lower() == "events":
            suggestions = await get_events_by_category(
                category, location, max_price, limit
            )
        else:
            return {
                "error": f"Invalid suggestion type: {suggestion_type}",
                "suggestions": []
            }
        
        # Convert to dictionary format
        suggestions_data = [suggestion.to_dict() for suggestion in suggestions]
        
        return {
            "suggestion_type": suggestion_type,
            "category": category,
            "total_suggestions": len(suggestions_data),
            "suggestions": suggestions_data
        }
        
    except Exception as e:
        return {
            "error": f"Failed to get suggestions: {str(e)}",
            "suggestion_type": suggestion_type,
            "category": category,
            "suggestions": []
        }

def generate_category_description(category: str) -> str:
    """Generate AI-powered description for each category"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        category_descriptions = {
            "adventurous": "Discover unique experiences and personalized options to elevate your adventure",
            "relax": "Unwind and rejuvenate with peaceful activities designed for relaxation",
            "luxurious": "Indulge in premium experiences and exclusive activities for the discerning traveler",
            "cultural": "Immerse yourself in local traditions and authentic cultural experiences"
        }
        
        if category.lower() in category_descriptions:
            return category_descriptions[category.lower()]
        
        # Generate custom description for unknown categories
        prompt = f"""
        Generate a short, engaging description (1 sentence) for a travel activity category called "{category}".
        The description should be exciting and make people want to explore this type of experience.
        Keep it under 20 words.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        return f"Explore amazing {category} experiences tailored just for you"
