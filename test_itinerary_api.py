#!/usr/bin/env python3
"""
Test script for the Travel AI Assistant API
"""

import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test the health check endpoint"""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_categories():
    """Test the categories endpoint"""
    print("Testing categories endpoint...")
    response = requests.get(f"{BASE_URL}/ai/categories")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print("Categories:")
        for category in data['data']['categories']:
            print(f"  - {category['display_name']}: {category['description']}")
    print()

def test_itinerary_analysis():
    """Test the itinerary analysis endpoint"""
    print("Testing itinerary analysis...")
    
    # Test with a sample user ID
    payload = {
        "user_id": 1
    }
    
    response = requests.post(
        f"{BASE_URL}/ai/itinerary/analyze",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data['message']}")
        if 'data' in data and 'free_time_slots' in data['data']:
            print(f"Free time slots found: {len(data['data']['free_time_slots'])}")
            for slot in data['data']['free_time_slots']:
                print(f"  - {slot['start_time']} to {slot['end_time']} ({slot['duration_minutes']} min)")
        if 'data' in data and 'contextual_message' in data['data']:
            print(f"Contextual message: {data['data']['contextual_message']}")
    else:
        print(f"Error: {response.text}")
    print()

def test_activity_suggestions():
    """Test the activity suggestions endpoint"""
    print("Testing activity suggestions...")
    
    # Test different categories and types
    test_cases = [
        {"suggestion_type": "activities", "category": "adventurous", "limit": 5},
        {"suggestion_type": "restaurants", "category": "luxurious", "limit": 3},
        {"suggestion_type": "nightlife", "category": "cultural", "limit": 3},
        {"suggestion_type": "events", "category": "relax", "limit": 3}
    ]
    
    for test_case in test_cases:
        print(f"Testing {test_case['suggestion_type']} - {test_case['category']}...")
        
        response = requests.post(
            f"{BASE_URL}/ai/activities/suggest",
            json=test_case,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Message: {data['message']}")
            if 'data' in data and 'suggestions' in data['data']:
                suggestions = data['data']['suggestions']
                print(f"Found {len(suggestions)} suggestions:")
                for suggestion in suggestions[:3]:  # Show first 3
                    print(f"  - {suggestion['title']} ({suggestion['location']})")
                    print(f"    Price: {suggestion['price_display']}, Rating: {suggestion['rating_display']}")
        else:
            print(f"Error: {response.text}")
        print()

def test_dish_assist():
    """Test the existing dish assistance endpoint"""
    print("Testing dish assistance...")
    
    payload = {
        "dish_name": "Eiffel Tower Summit Tour"
    }
    
    response = requests.post(
        f"{BASE_URL}/ai/dish/assist",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Message: {data['message']}")
        if 'data' in data and 'ai_response' in data['data']:
            print(f"AI Response: {data['data']['ai_response'][:200]}...")
    else:
        print(f"Error: {response.text}")
    print()

def main():
    """Run all tests"""
    print("=" * 50)
    print("Travel AI Assistant API Test Suite")
    print("=" * 50)
    print()
    
    try:
        # Test health check
        test_health_check()
        
        # Test categories
        test_categories()
        
        # Test itinerary analysis
        test_itinerary_analysis()
        
        # Test activity suggestions
        test_activity_suggestions()
        
        # Test dish assistance (existing functionality)
        test_dish_assist()
        
        print("=" * 50)
        print("All tests completed!")
        print("=" * 50)
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the API server.")
        print("Make sure the server is running on http://localhost:8000")
    except Exception as e:
        print(f"Error running tests: {str(e)}")

if __name__ == "__main__":
    main()
