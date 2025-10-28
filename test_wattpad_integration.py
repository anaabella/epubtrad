#!/usr/bin/env python3
import requests
import re
import os

def test_wattpad_url_extraction():
    """Test story ID extraction from various Wattpad URL formats"""
    test_urls = [
        "https://www.wattpad.com/story/123456789-test-story",
        "https://www.wattpad.com/story/123456789-test-story-chapter-1",
        "https://www.wattpad.com/user/story/123456789-test-story",
        "https://www.wattpad.com/123456789-test-story",
        "https://www.wattpad.com/story/969099212-the-way-i-hate-you-park-sunghoon-chapter-1"
    ]

    print("=== Testing Wattpad URL Extraction ===")
    for url in test_urls:
        match = re.search(r'wattpad\.com/story/(\d+)', url)
        if match:
            story_id = match.group(1)
            print(f"✅ URL: {url}")
            print(f"   Extracted ID: {story_id}")
        else:
            print(f"❌ URL: {url}")
            print("   No ID extracted")
    print()

def test_api_connection():
    """Test connection to deployed Wattpad API"""
    WATTPAD_API_URL = os.environ.get("WATTPAD_API_URL", "https://wattpad-downloader-e27u.onrender.com")

    print("=== Testing API Connection ===")
    try:
        # Test health endpoint
        health_url = f"{WATTPAD_API_URL}/health"
        response = requests.get(health_url, timeout=10)
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print("❌ API health check failed")

        # Test download endpoint with a known story ID
        test_story_id = "969099212"  # From debug_wattpad.py
        download_url = f"{WATTPAD_API_URL}/api/{test_story_id}/download/epub"
        print(f"Testing download URL: {download_url}")

        response = requests.get(download_url, timeout=60)
        print(f"Download response: {response.status_code}")

        if response.status_code == 200:
            print("✅ API download successful")
            print(f"Response size: {len(response.content)} bytes")
            # Check if it's a valid EPUB (starts with PK header for ZIP)
            if response.content.startswith(b'PK'):
                print("✅ Response appears to be a valid EPUB file")
            else:
                print("⚠️ Response may not be a valid EPUB file")
        else:
            print(f"❌ API download failed: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"❌ API connection error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    print()

def test_error_handling():
    """Test error handling for invalid inputs"""
    WATTPAD_API_URL = os.environ.get("WATTPAD_API_URL", "https://wattpad-downloader-e27u.onrender.com")

    print("=== Testing Error Handling ===")
    invalid_ids = ["999999999999999", "invalid", "0", "-1"]

    for story_id in invalid_ids:
        try:
            download_url = f"{WATTPAD_API_URL}/api/{story_id}/download/epub"
            response = requests.get(download_url, timeout=30)
            print(f"ID {story_id}: Status {response.status_code}")
            if response.status_code == 404:
                print("✅ Correctly handled invalid story ID")
            elif response.status_code == 200:
                print("⚠️ Unexpected success for invalid ID")
            else:
                print(f"⚠️ Unexpected status code: {response.status_code}")
        except Exception as e:
            print(f"❌ Error testing ID {story_id}: {e}")
    print()

if __name__ == "__main__":
    print("Starting Wattpad Integration Tests\n")
    test_wattpad_url_extraction()
    test_api_connection()
    test_error_handling()
    print("Tests completed!")
