#!/usr/bin/env python3
"""
Test the updated keyword-based API
"""

import requests
import json
import time

API_BASE = "http://localhost:8000"

def test_keyword_api():
    print("Testing Updated Keyword-Based API")
    print("=" * 50)
    
    # Test 1: Check API status
    print("\n1. Testing API Status...")
    try:
        response = requests.get(f"{API_BASE}/")
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: API Status: {data['status']}")
            print(f"SUCCESS: Available endpoints: {list(data['endpoints'].keys())}")
        else:
            print(f"ERROR: API Error: {response.status_code}")
            return
    except Exception as e:
        print(f"ERROR: Connection Error: {e}")
        print("Make sure the API server is running!")
        return
    
    # Test 2: Check search examples
    print("\n2. Testing Search Examples...")
    try:
        response = requests.get(f"{API_BASE}/search-examples")
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Search examples: {data['examples'][:5]}...")
            print(f"SUCCESS: Note: {data['note']}")
        else:
            print(f"ERROR: Search examples error: {response.status_code}")
    except Exception as e:
        print(f"ERROR: Search examples error: {e}")
    
    # Test 3: Start a keyword search job
    print("\n3. Testing Keyword Search Job...")
    try:
        search_data = {
            "keyword": "iPhone 15",
            "search_type": "keyword"
        }
        
        response = requests.post(f"{API_BASE}/scrape/keyword", json=search_data)
        if response.status_code == 200:
            job_data = response.json()
            job_id = job_data['job_id']
            print(f"SUCCESS: Job started: {job_id}")
            print(f"SUCCESS: Status: {job_data['status']}")
            print(f"SUCCESS: Message: {job_data['message']}")
            
            # Test 4: Check job status
            print(f"\n4. Checking Job Status...")
            time.sleep(2)  # Wait a bit
            
            status_response = requests.get(f"{API_BASE}/jobs/{job_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                print(f"SUCCESS: Job Status: {status_data['status']}")
                print(f"SUCCESS: Progress: {status_data['progress']}%")
                print(f"SUCCESS: Message: {status_data['message']}")
            else:
                print(f"ERROR: Status check error: {status_response.status_code}")
                
        else:
            print(f"ERROR: Job start error: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"ERROR: Job test error: {e}")
    
    print("\n" + "=" * 50)
    print("API Test Complete!")
    print("\nTo use the API:")
    print("1. POST /scrape/keyword with {'keyword': 'your search term'}")
    print("2. GET /jobs/{job_id} to check status")
    print("3. GET /download/{job_id}/csv to download results")

if __name__ == "__main__":
    test_keyword_api()
