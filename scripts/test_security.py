#!/usr/bin/env python3
"""
Quick security test script to validate the hardening measures.
Run this script to verify that the security controls are working properly.
"""

import os
import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = os.environ.get("LLM_API_KEY", "test-api-key-12345")

def test_no_api_key():
    """Test that requests without API key return 403."""
    print("Testing: No API Key...")
    response = requests.post(f"{BASE_URL}/api/v1/chat", json={"message": "Hello"})
    if response.status_code == 403:
        print("✅ PASS - Returns 403 without API key")
    else:
        print(f"❌ FAIL - Expected 403, got {response.status_code}")
    return response.status_code == 403

def test_valid_api_key():
    """Test that valid API key works."""
    print("\nTesting: Valid API Key...")
    headers = {"X-API-Key": API_KEY}
    response = requests.post(f"{BASE_URL}/api/v1/chat", json={"message": "Hello"}, headers=headers)
    if response.status_code != 403:
        print(f"✅ PASS - Authentication successful (status: {response.status_code})")
    else:
        print("❌ FAIL - Valid API key rejected")
    return response.status_code != 403

def test_oversized_payload():
    """Test that oversized payload is rejected."""
    print("\nTesting: Oversized Payload...")
    headers = {"X-API-Key": API_KEY}
    large_payload = {"message": "a" * 10001}
    response = requests.post(f"{BASE_URL}/api/v1/chat", json=large_payload, headers=headers)
    if response.status_code == 422:
        print("✅ PASS - Oversized payload rejected with 422")
    else:
        print(f"❌ FAIL - Expected 422, got {response.status_code}")
    return response.status_code == 422

def test_health_check():
    """Test that health check works without auth."""
    print("\nTesting: Health Check (No Auth Required)...")
    response = requests.get(f"{BASE_URL}/api/v1/health")
    if response.status_code == 200:
        print("✅ PASS - Health check accessible without auth")
    else:
        print(f"❌ FAIL - Expected 200, got {response.status_code}")
    return response.status_code == 200

def main():
    """Run all security tests."""
    print("=" * 50)
    print("SECURITY HARDENING VALIDATION")
    print("=" * 50)
    print(f"Testing API at: {BASE_URL}")
    print(f"Using API Key: {API_KEY[:8]}...")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Server not running at {BASE_URL}")
        print("Please start the server first: python -m app.main")
        return
    
    # Run tests
    results = []
    results.append(test_no_api_key())
    results.append(test_valid_api_key())
    results.append(test_oversized_payload())
    results.append(test_health_check())
    
    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All security tests passed!")
    else:
        print("⚠️  Some security tests failed. Review the implementation.")
    
    print("\nTo run the full test suite:")
    print("  pytest tests/security/test_hardening.py -v")

if __name__ == "__main__":
    main()
