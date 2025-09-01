from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import io
import logging

from ai_services import dish_descriptor
from tts_service import get_pronunciation_audio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Dish Insight AI API",
    description="AI-powered dish description and pronunciation service",
    version="1.0.0"
)

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

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Dish Insight AI API is running"}

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
