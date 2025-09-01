import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def dish_descriptor(dish_name, question=None):
    """
    Generate dish description using Gemini AI
    
    Args:
        dish_name (str): Name of the dish
        question (str, optional): Specific question about the dish
    
    Returns:
        str: AI-generated response about the dish
    """
    try:
        # Create the model
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if question:
            # Interactive Q&A mode
            prompt = f"""You are a professional culinary expert. For the dish "{dish_name}", please answer this specific question: {question}
            
            Provide a concise, relevant answer that directly addresses the question."""
        else:
            # Default rich info mode
            prompt = f"""You are a professional culinary expert. For the dish "{dish_name}", please provide the following information in a structured format:

            1. Dish pronunciation (text format)
            2. Key ingredients and preparation style
            3. Spice level (mild/medium/hot)
            4. Allergen warnings and dietary suitability
            5. Suggested drink pairing
            6. One-sentence cultural or regional background

            Format your response clearly with each section labeled."""
        
        # Generate content
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"Error generating dish description: {str(e)}"
