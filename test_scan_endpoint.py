#!/usr/bin/env python3
"""
Test script to verify the scan endpoint is working.
Run this while the web server is running.
"""

import requests
import json
import sys
import time

def test_scan_endpoint():
    """Test the scan API endpoint."""
    base_url = "http://localhost:5000"
    
    print("Testing File Categorizer Scan Endpoint")
    print("=" * 50)
    
    # Test 1: Check if scan endpoint exists
    try:
        response = requests.get(f"{base_url}/api/scan/status", timeout=5)
        print(f"✓ Scan status endpoint accessible: {response.status_code}")
    except Exception as e:
        print(f"✗ Scan status endpoint error: {e}")
        return False
    
    # Test 2: Try to start a scan with invalid path
    try:
        response = requests.post(f"{base_url}/api/scan", 
                               json={"path": "/nonexistent/path"}, 
                               timeout=5)
        print(f"✓ Scan endpoint responds to POST: {response.status_code}")
        
        if response.status_code == 400:
            data = response.json()
            print(f"✓ Correctly rejects invalid path: {data.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"✗ Scan POST endpoint error: {e}")
        return False
    
    # Test 3: Check what happens with empty request
    try:
        response = requests.post(f"{base_url}/api/scan", 
                               json={}, 
                               timeout=5)
        print(f"✓ Scan endpoint handles empty request: {response.status_code}")
        
        if response.status_code == 400:
            data = response.json()
            print(f"✓ Correctly requires path: {data.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"✗ Empty request test error: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("Scan endpoint tests completed!")
    print("\nTo test with a real directory:")
    print("1. Make sure you enter a valid directory path in the web interface")
    print("2. Check browser console (F12) for any JavaScript errors")
    print("3. Look for toast notifications in the top-right corner")
    
    return True

if __name__ == "__main__":
    if not test_scan_endpoint():
        print("\n❌ Some tests failed. Make sure the web server is running.")
        sys.exit(1)
    else:
        print("\n✅ Basic scan endpoint functionality is working!")
        sys.exit(0)