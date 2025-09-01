# Dish Insight AI API

A FastAPI-based AI service that provides comprehensive dish information including pronunciation, ingredients, spice level, allergen warnings, drink pairings, and cultural background using Google Gemini AI and Azure Text-to-Speech.

## Features

- **AI-Powered Dish Descriptions**: Get rich information about any dish using Google Gemini AI
- **Interactive Q&A**: Ask specific questions about dishes
- **Pronunciation Audio**: Generate audio pronunciation using Azure TTS
- **Fast Response**: All responses under 2 seconds
- **Docker Support**: Easy deployment with Docker and Docker Compose

## API Endpoints

### 1. `/ai/dish/assist` (POST)
Get comprehensive dish information or answer specific questions.

**Request:**
```json
{
  "dish_name": "Pad Thai",
  "question": "What's in this dish?" // Optional
}
```

**Response:**
```json
{
  "status": true,
  "message": "Retrieved dish description successfully",
  "data": {
    "ai_response": "Comprehensive dish information..."
  }
}
```

### 2. `/ai/dish/pronunciation` (POST)
Generate pronunciation audio for any text.

**Request:**
```json
{
  "text": "Pad Thai"
}
```

**Response:** Audio file (WAV format)

### 3. `/ai/dish/pronunciation/{dish_name}` (POST)
Generate pronunciation audio for a specific dish name.

**Response:** Audio file (WAV format)

### 4. `/health` (GET)
Health check endpoint.

## Setup

### Prerequisites
- Python 3.11+
- Docker (optional)
- Google Gemini API key
- Azure Speech Services API key

### Environment Variables
Create a `.env` file with the following variables:

```env
GEMINI_API_KEY=your_gemini_api_key
SPEECH_KEY=your_azure_speech_key
SPEECH_KEY_BACKUP=your_backup_azure_speech_key
ENDPOINT_URL=endpoint
```

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd dish-insight
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Deployment

1. **Build and run with Docker Compose**
   ```bash
   docker-compose up --build
   ```

2. **Or build and run with Docker**
   ```bash
   docker build -t dish-insight-api .
   docker run -p 8000:8000 --env-file .env dish-insight-api
   ```

## Usage Examples

### Get Default Dish Information
```bash
curl -X POST "http://localhost:8000/ai/dish/assist" \
     -H "Content-Type: application/json" \
     -d '{"dish_name": "Pad Thai"}'
```

### Ask Specific Question
```bash
curl -X POST "http://localhost:8000/ai/dish/assist" \
     -H "Content-Type: application/json" \
     -d '{"dish_name": "Pad Thai", "question": "How spicy is it?"}'
```

### Get Pronunciation Audio
```bash
curl -X POST "http://localhost:8000/ai/dish/pronunciation" \
     -H "Content-Type: application/json" \
     -d '{"text": "Pad Thai"}' \
     --output pronunciation.wav
```

## Default AI Responses

When no specific question is asked, the AI provides:

1. **Dish pronunciation** (text format)
2. **Key ingredients and preparation style**
3. **Spice level** (mild/medium/hot)
4. **Allergen warnings and dietary suitability**
5. **Suggested drink pairing**
6. **One-sentence cultural or regional background**

## Interactive Q&A Examples

Users can ask questions like:
- "What's in this dish?"
- "How spicy is it?"
- "What drink goes well with it?"
- "Is this suitable for vegetarians?"
- "What's the origin of this dish?"

## Performance & Reliability

- **Response Time**: All responses under 2 seconds
- **Uptime**: Designed for ≥99% availability
- **Fallback**: Graceful error handling with fallback responses
- **Security**: Secure API authentication required
- **Privacy**: No PII stored or returned

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.
