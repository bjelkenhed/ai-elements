#!/usr/bin/env python3
"""
Simple test script for the FastAPI chat endpoint
"""
import requests
import json
import sys

def test_health_endpoint():
    """Test the health endpoint"""
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"Health check status: {response.status_code}")
        print(f"Health response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_chat_endpoint():
    """Test the chat endpoint with a simple message"""
    payload = {
        "messages": [
            {
                "id": "test-1",
                "role": "user",
                "content": "Hello! Please respond with a simple greeting."
            }
        ],
        "model": "openai/gpt-4o",
        "webSearch": False
    }

    try:
        response = requests.post(
            "http://localhost:8000/chat",
            json=payload,
            stream=True,
            headers={"Content-Type": "application/json"}
        )

        print(f"Chat endpoint status: {response.status_code}")
        print("Streaming response:")

        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_str = line_str[6:]  # Remove 'data: ' prefix
                    try:
                        data = json.loads(data_str)
                        print(f"  {data}")
                    except json.JSONDecodeError:
                        print(f"  Raw: {data_str}")

        return True

    except Exception as e:
        print(f"Chat endpoint test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing FastAPI endpoints...")

    if not test_health_endpoint():
        print("Health endpoint failed. Is the server running?")
        sys.exit(1)

    print("\nTesting chat endpoint...")
    if test_chat_endpoint():
        print("Chat endpoint test completed!")
    else:
        print("Chat endpoint test failed!")
        sys.exit(1)