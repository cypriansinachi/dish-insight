#!/usr/bin/env python3
"""
Simple test script for the Dish Insight AI API
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_dish_assist_default():
    """Test dish assist with default response"""
    print("\nTesting dish assist (default response)...")
    try:
        payload = {"dish_name": "Pad Thai"}
        response = requests.post(f"{BASE_URL}/ai/dish/assist", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data['status']}")
            print(f"Message: {data['message']}")
            print(f"AI Response: {data['data']['ai_response'][:200]}...")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Dish assist test failed: {e}")
        return False

def test_dish_assist_question():
    """Test dish assist with specific question"""
    print("\nTesting dish assist (with question)...")
    try:
        payload = {"dish_name": "Pad Thai", "question": "How spicy is it?"}
        response = requests.post(f"{BASE_URL}/ai/dish/assist", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data['status']}")
            print(f"AI Response: {data['data']['ai_response']}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Dish assist question test failed: {e}")
        return False

def test_pronunciation():
    """Test pronunciation endpoint"""
    print("\nTesting pronunciation endpoint...")
    try:
        payload = {"text": "Pad Thai"}
        response = requests.post(f"{BASE_URL}/ai/dish/pronunciation", json=payload)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            # Save audio file
            with open("test_pronunciation.wav", "wb") as f:
                f.write(response.content)
            print("Audio file saved as test_pronunciation.wav")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Pronunciation test failed: {e}")
        return False

def test_dish_pronunciation():
    """Test dish-specific pronunciation endpoint"""
    print("\nTesting dish pronunciation endpoint...")
    try:
        response = requests.post(f"{BASE_URL}/ai/dish/pronunciation/Pad%20Thai")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            # Save audio file
            with open("test_dish_pronunciation.wav", "wb") as f:
                f.write(response.content)
            print("Audio file saved as test_dish_pronunciation.wav")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Dish pronunciation test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Dish Insight AI API Test Suite")
    print("=" * 40)
    
    tests = [
        test_health,
        test_dish_assist_default,
        test_dish_assist_question,
        test_pronunciation,
        test_dish_pronunciation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print("-" * 40)
    
    print(f"\nTest Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! 🎉")
    else:
        print("Some tests failed. Check the output above.")

if __name__ == "__main__":
    main()
