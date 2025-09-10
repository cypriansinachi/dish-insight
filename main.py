from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import io
import logging

from ai_services import dish_descriptor
from tts_service import get_pronunciation_audio
from itinerary_ai_service import analyze_user_itinerary
from activity_suggestion_service import get_suggestions_by_type_and_category, generate_category_description
from db_connection import init_pool, close_pool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Travel AI Assistant API",
    description="AI-powered travel itinerary analysis and activity suggestions",
    version="1.0.0"
)

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database connection pool on startup"""
    await init_pool()
    logger.info("Database connection pool initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Close database connection pool on shutdown"""
    await close_pool()
    logger.info("Database connection pool closed")

# Request/Response Models
class DishAssistRequest(BaseModel):
    dish_name: str
    question: Optional[str] = None

class DishAssistResponse(BaseModel):
    status: bool
    message: str
    data: dict

class PronunciationRequest(BaseModel):
    text: str

# New models for itinerary analysis
class ItineraryAnalysisRequest(BaseModel):
    user_id: int

class ItineraryAnalysisResponse(BaseModel):
    status: bool
    message: str
    data: dict

class ActivitySuggestionRequest(BaseModel):
    suggestion_type: str  # activities, restaurants, nightlife, events
    category: str  # adventurous, relax, luxurious, cultural
    location: Optional[str] = None
    duration_minutes: Optional[int] = None
    max_price: Optional[float] = None
    limit: Optional[int] = 20

class ActivitySuggestionResponse(BaseModel):
    status: bool
    message: str
    data: dict

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Travel AI Assistant API is running"}

# Itinerary Analysis Endpoints
@app.post("/ai/itinerary/analyze", response_model=ItineraryAnalysisResponse)
async def analyze_itinerary(request: ItineraryAnalysisRequest):
    """
    Analyze user itinerary to find free time slots
    
    This endpoint:
    - Fetches all active bookings for the user
    - Analyzes the schedule to identify free time windows
    - Returns contextual suggestions for activities
    """
    try:
        logger.info(f"Processing itinerary analysis request for user: {request.user_id}")
        
        # Validate input
        if not request.user_id or request.user_id <= 0:
            raise HTTPException(status_code=400, detail="Valid user_id is required")
        
        # Analyze itinerary
        result = await analyze_user_itinerary(request.user_id)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return ItineraryAnalysisResponse(
            status=True,
            message="Itinerary analyzed successfully",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analyze_itinerary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/ai/activities/suggest", response_model=ActivitySuggestionResponse)
async def suggest_activities(request: ActivitySuggestionRequest):
    """
    Get activity suggestions based on category and preferences
    
    This endpoint:
    - Takes a category (adventurous, relax, luxurious, cultural)
    - Takes a suggestion type (activities, restaurants, nightlife, events)
    - Returns filtered suggestions based on user preferences
    """
    try:
        logger.info(f"Processing activity suggestion request: {request.category} - {request.suggestion_type}")
        
        # Validate input
        valid_categories = ["adventurous", "relax", "luxurious", "cultural"]
        valid_types = ["activities", "restaurants", "nightlife", "events"]
        
        if request.category.lower() not in valid_categories:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid category. Must be one of: {', '.join(valid_categories)}"
            )
        
        if request.suggestion_type.lower() not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid suggestion_type. Must be one of: {', '.join(valid_types)}"
            )
        
        # Get suggestions
        result = await get_suggestions_by_type_and_category(
            suggestion_type=request.suggestion_type,
            category=request.category,
            location=request.location,
            duration_minutes=request.duration_minutes,
            max_price=request.max_price,
            limit=request.limit
        )
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Add category description
        result["category_description"] = generate_category_description(request.category)
        
        return ActivitySuggestionResponse(
            status=True,
            message=f"Found {result['total_suggestions']} {request.suggestion_type} suggestions",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in suggest_activities: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/ai/categories")
async def get_categories():
    """
    Get available activity categories with descriptions
    """
    try:
        categories = [
            {
                "name": "adventurous",
                "display_name": "Adventurous",
                "description": generate_category_description("adventurous"),
                "icon": "mountain"
            },
            {
                "name": "relax",
                "display_name": "Relax",
                "description": generate_category_description("relax"),
                "icon": "umbrella"
            },
            {
                "name": "luxurious",
                "display_name": "Luxurious",
                "description": generate_category_description("luxurious"),
                "icon": "diamond"
            },
            {
                "name": "cultural",
                "display_name": "Cultural",
                "description": generate_category_description("cultural"),
                "icon": "temple"
            }
        ]
        
        return {
            "status": True,
            "message": "Categories retrieved successfully",
            "data": {
                "categories": categories,
                "suggestion_types": [
                    {"name": "activities", "display_name": "Activities"},
                    {"name": "restaurants", "display_name": "Restaurants"},
                    {"name": "nightlife", "display_name": "Nightlife"},
                    {"name": "events", "display_name": "Events"}
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"Error in get_categories: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Main dish assistance endpoint
@app.post("/ai/dish/assist", response_model=DishAssistResponse)
async def dish_assist(request: DishAssistRequest):
    """
    AI-powered dish assistance endpoint
    
    Provides comprehensive dish information including:
    - Pronunciation (text + audio)
    - Key ingredients and preparation style
    - Spice level
    - Allergen warnings and dietary suitability
    - Suggested drink pairing
    - Cultural/regional background
    
    Or answers specific questions about the dish.
    """
    try:
        logger.info(f"Processing dish assist request for: {request.dish_name}")
        
        # Validate input
        if not request.dish_name or not request.dish_name.strip():
            raise HTTPException(status_code=400, detail="Dish name is required")
        
        # Get AI response
        ai_response = dish_descriptor(request.dish_name.strip(), request.question)
        
        if not ai_response:
            raise HTTPException(status_code=500, detail="Failed to generate AI response")
        
        return DishAssistResponse(
            status=True,
            message="Retrieved dish description successfully",
            data={"ai_response": ai_response}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in dish_assist: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Pronunciation endpoint
@app.post("/ai/dish/pronunciation")
async def get_pronunciation(request: PronunciationRequest):
    """
    Generate pronunciation audio for text
    
    Returns audio file as streaming response
    """
    try:
        logger.info(f"Processing pronunciation request for: {request.text}")
        
        # Validate input
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text is required")
        
        # Generate audio
        audio_data = get_pronunciation_audio(request.text.strip())
        
        if not audio_data:
            raise HTTPException(status_code=500, detail="Failed to generate pronunciation audio")
        
        # Create audio stream
        audio_stream = io.BytesIO(audio_data)
        
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename=pronunciation_{request.text.replace(' ', '_')}.wav"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_pronunciation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Alternative pronunciation endpoint for dish names specifically
@app.post("/ai/dish/pronunciation/{dish_name}")
async def get_dish_pronunciation(dish_name: str):
    """
    Generate pronunciation audio for a specific dish name
    
    Returns audio file as streaming response
    """
    try:
        logger.info(f"Processing dish pronunciation request for: {dish_name}")
        
        # Validate input
        if not dish_name or not dish_name.strip():
            raise HTTPException(status_code=400, detail="Dish name is required")
        
        # Generate audio
        audio_data = get_pronunciation_audio(dish_name.strip())
        
        if not audio_data:
            raise HTTPException(status_code=500, detail="Failed to generate pronunciation audio")
        
        # Create audio stream
        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename={dish_name.replace(' ', '_')}_pronunciation.wav"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_dish_pronunciation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
