# Travel AI Assistant API

This API provides AI-powered travel itinerary analysis and activity suggestions based on user preferences and free time slots.

## Features

### 1. Itinerary Analysis
- Analyzes user's active bookings (hotels, flights, activities)
- Identifies free time slots in the schedule
- Generates contextual messages about available time
- Returns structured data about free time windows

### 2. Activity Suggestions
- Suggests activities based on user preferences (adventurous, relax, luxurious, cultural)
- Supports multiple suggestion types: activities, restaurants, nightlife, events
- Filters by location, duration, and price
- Returns detailed activity information with ratings and pricing

## API Endpoints

### Health Check
```
GET /health
```
Returns API status and health information.

### Itinerary Analysis
```
POST /ai/itinerary/analyze
```
Analyzes a user's itinerary to find free time slots.

**Request Body:**
```json
{
  "user_id": 1
}
```

**Response:**
```json
{
  "status": true,
  "message": "Itinerary analyzed successfully",
  "data": {
    "user_id": 1,
    "total_bookings": 3,
    "free_time_slots": [
      {
        "start_time": "15:00",
        "end_time": "19:00",
        "duration_minutes": 240,
        "context": "Gap between bookings"
      }
    ],
    "contextual_message": "You've got some free time between 3 PM and 7 PM. What kind of experience are you in the mood for?",
    "bookings": [...]
  }
}
```

### Activity Suggestions
```
POST /ai/activities/suggest
```
Get activity suggestions based on category and preferences.

**Request Body:**
```json
{
  "suggestion_type": "activities",
  "category": "adventurous",
  "location": "Paris, France",
  "duration_minutes": 180,
  "max_price": 50000,
  "limit": 20
}
```

**Response:**
```json
{
  "status": true,
  "message": "Found 15 activities suggestions",
  "data": {
    "suggestion_type": "activities",
    "category": "adventurous",
    "total_suggestions": 15,
    "category_description": "Discover unique experiences and personalized options to elevate your adventure",
    "suggestions": [
      {
        "activity_id": 123,
        "title": "Eiffel Tower Summit Tour",
        "location": "Paris, France",
        "duration_minutes": 165,
        "duration_display": "2h 45m",
        "price": 123450.00,
        "price_display": "₦123,450.00",
        "rating": 8.5,
        "rating_display": "8.5 (425)",
        "category": "adventure",
        "description": "Experience the iconic Eiffel Tower from its summit",
        "image_url": "https://example.com/image.jpg",
        "provider": "B. Booking",
        "availability": "Flexible dates"
      }
    ]
  }
}
```

### Get Categories
```
GET /ai/categories
```
Get available activity categories and suggestion types.

**Response:**
```json
{
  "status": true,
  "message": "Categories retrieved successfully",
  "data": {
    "categories": [
      {
        "name": "adventurous",
        "display_name": "Adventurous",
        "description": "Discover unique experiences and personalized options to elevate your adventure",
        "icon": "mountain"
      },
      {
        "name": "relax",
        "display_name": "Relax",
        "description": "Unwind and rejuvenate with peaceful activities designed for relaxation",
        "icon": "umbrella"
      },
      {
        "name": "luxurious",
        "display_name": "Luxurious",
        "description": "Indulge in premium experiences and exclusive activities for the discerning traveler",
        "icon": "diamond"
      },
      {
        "name": "cultural",
        "display_name": "Cultural",
        "description": "Immerse yourself in local traditions and authentic cultural experiences",
        "icon": "temple"
      }
    ],
    "suggestion_types": [
      {"name": "activities", "display_name": "Activities"},
      {"name": "restaurants", "display_name": "Restaurants"},
      {"name": "nightlife", "display_name": "Nightlife"},
      {"name": "events", "display_name": "Events"}
    ]
  }
}
```

## Database Schema

The API expects the following database tables:

### Hotel Bookings
```sql
CREATE TABLE hotel_bookings (
    id INT PRIMARY KEY,
    user_id INT,
    hotel_name VARCHAR(255),
    location VARCHAR(255),
    check_in_date DATE,
    check_out_date DATE,
    check_in_time TIME,
    check_out_time TIME,
    booking_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Flight Bookings
```sql
CREATE TABLE flight_bookings (
    id INT PRIMARY KEY,
    user_id INT,
    departure_city VARCHAR(100),
    arrival_city VARCHAR(100),
    departure_date DATE,
    arrival_date DATE,
    departure_time TIME,
    arrival_time TIME,
    flight_duration_minutes INT,
    booking_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Activity Bookings
```sql
CREATE TABLE activity_bookings (
    id INT PRIMARY KEY,
    user_id INT,
    activity_name VARCHAR(255),
    location VARCHAR(255),
    activity_date DATE,
    start_time TIME,
    end_time TIME,
    duration_minutes INT,
    booking_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Activities
```sql
CREATE TABLE activities (
    id INT PRIMARY KEY,
    title VARCHAR(255),
    location VARCHAR(255),
    duration_minutes INT,
    price DECIMAL(10,2),
    rating DECIMAL(3,1),
    category VARCHAR(50),
    description TEXT,
    image_url VARCHAR(500),
    provider VARCHAR(100),
    availability VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Restaurants
```sql
CREATE TABLE restaurants (
    id INT PRIMARY KEY,
    restaurant_name VARCHAR(255),
    location VARCHAR(255),
    estimated_duration_minutes INT,
    average_price DECIMAL(10,2),
    rating DECIMAL(3,1),
    cuisine_type VARCHAR(50),
    description TEXT,
    image_url VARCHAR(500),
    provider VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Nightlife Venues
```sql
CREATE TABLE nightlife_venues (
    id INT PRIMARY KEY,
    venue_name VARCHAR(255),
    location VARCHAR(255),
    cover_charge DECIMAL(10,2),
    rating DECIMAL(3,1),
    venue_type VARCHAR(50),
    description TEXT,
    image_url VARCHAR(500),
    provider VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active'
);
```

### Events
```sql
CREATE TABLE events (
    id INT PRIMARY KEY,
    event_name VARCHAR(255),
    location VARCHAR(255),
    event_date DATE,
    duration_minutes INT,
    ticket_price DECIMAL(10,2),
    rating DECIMAL(3,1),
    event_type VARCHAR(50),
    description TEXT,
    image_url VARCHAR(500),
    organizer VARCHAR(100),
    status VARCHAR(20) DEFAULT 'active'
);
```

## Environment Variables

Create a `.env` file with the following variables:

```env
# Database Configuration
DB_CONNECTION=mysql
DB_HOST=your_database_host
DB_PORT=3306
DB_DATABASE=your_database_name
DB_USERNAME=your_username
DB_PASSWORD=your_password

# AI Configuration
GEMINI_API_KEY=your_gemini_api_key
SPEECH_KEY=your_speech_key
ENDPOINT_URL=your_endpoint_url
```

## Installation and Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your `.env` file with database credentials and API keys

3. Start the server:
```bash
python start.py
```

4. Test the API:
```bash
python test_itinerary_api.py
```

## Usage Examples

### Frontend Integration

The API is designed to work with the UI shown in the images:

1. **Active Bookings Page**: Call `/ai/itinerary/analyze` to get free time slots and display the contextual message
2. **Activity Selection**: When user clicks on a category (adventurous, relax, etc.), call `/ai/activities/suggest` with the selected category
3. **Category Display**: Use `/ai/categories` to get category information and descriptions

### Example Frontend Flow

```javascript
// 1. Analyze user itinerary
const itineraryResponse = await fetch('/ai/itinerary/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ user_id: 1 })
});

const itineraryData = await itineraryResponse.json();
// Display contextual message and free time slots

// 2. When user selects "Adventurous" category
const activityResponse = await fetch('/ai/activities/suggest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    suggestion_type: 'activities',
    category: 'adventurous',
    limit: 20
  })
});

const activityData = await activityResponse.json();
// Display activity suggestions in the UI
```

## Error Handling

The API returns appropriate HTTP status codes:
- `200`: Success
- `400`: Bad Request (invalid parameters)
- `500`: Internal Server Error

All responses include a `status` field and descriptive error messages in the `message` field.
