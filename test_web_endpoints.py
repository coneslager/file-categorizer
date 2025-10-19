#!/usr/bin/env python3
"""
Test script to verify web endpoints are working.
Run this while the web server is running.
"""

import requests
import time
import sys

def test_endpoint(url, method='GET', data=None):
    """Test a single endpoint."""
    try:
        if method == 'GET':
            response = requests.get(url, timeout=5)
        elif method == 'POST':
            response = requests.post(url, json=data, timeout=5)
        
        print(f"✓ {method} {url} -> {response.status_code}")
        return response.status_code < 400
        
    except requests.exceptions.ConnectionError:
        print(f"✗ {method} {url} -> Connection refused (server not running?)")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ {method} {url} -> Timeout")
        return False
    except Exception as e:
        print(f"✗ {method} {url} -> Error: {e}")
        return False

def main():
    """Test all important endpoints."""
    base_url = "http://localhost:5000"
    
    print("Testing File Categorizer Web Endpoints")
    print("=" * 50)
    
    # Test basic pages
    endpoints = [
        ("GET", "/"),
        ("GET", "/scan"),
        ("GET", "/search"),
        ("GET", "/cleanup"),
        ("GET", "/api/files"),
        ("GET", "/api/files/stats"),
        ("GET", "/api/scan/status"),
        ("GET", "/api/cleanup/status"),
    ]
    
    passed = 0
    total = len(endpoints)
    
    for method, path in endpoints:
        url = base_url + path
        if test_endpoint(url, method):
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} endpoints working")
    
    if passed < total:
        print("\nTroubleshooting:")
        print("1. Make sure the web server is running: file-categorizer web --debug")
        print("2. Check that the server is listening on localhost:5000")
        print("3. Look for error messages in the server console")
        return 1
    else:
        print("✓ All basic endpoints are working!")
        
        # Test SSE endpoint (this might timeout, which is normal)
        print("\nTesting Server-Sent Events endpoint...")
        try:
            response = requests.get(f"{base_url}/api/progress/scan", 
                                  stream=True, timeout=2)
            print(f"✓ SSE endpoint accessible (status: {response.status_code})")
        except requests.exceptions.Timeout:
            print("✓ SSE endpoint accessible (timeout expected for streaming)")
        except Exception as e:
            print(f"✗ SSE endpoint error: {e}")
        
        return 0

if __name__ == "__main__":
    sys.exit(main())