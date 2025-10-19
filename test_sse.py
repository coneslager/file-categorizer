#!/usr/bin/env python3
"""
Test SSE endpoint directly.
"""

import requests
import time

def test_sse():
    """Test the SSE endpoint."""
    print("Testing SSE endpoint...")
    
    try:
        # Test SSE endpoint
        response = requests.get("http://localhost:5000/api/progress/scan", 
                              stream=True, timeout=5)
        
        print(f"SSE Status: {response.status_code}")
        print(f"SSE Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("SSE Content (first few lines):")
            lines_read = 0
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    print(f"  {line}")
                    lines_read += 1
                    if lines_read >= 5:  # Just read first 5 lines
                        break
        else:
            print(f"SSE Error: {response.text}")
            
    except requests.exceptions.Timeout:
        print("SSE Timeout (this might be normal)")
    except Exception as e:
        print(f"SSE Error: {e}")

def test_scan_and_sse():
    """Start a scan and monitor SSE."""
    print("\nTesting scan + SSE...")
    
    # Start a small scan
    try:
        response = requests.post("http://localhost:5000/api/scan", json={
            "path": "C:\\Windows\\System32",  # Small directory
            "recursive": False
        })
        
        if response.status_code == 200:
            print("✓ Scan started")
            
            # Now test SSE
            try:
                sse_response = requests.get("http://localhost:5000/api/progress/scan", 
                                          stream=True, timeout=10)
                
                print(f"SSE Status: {sse_response.status_code}")
                
                if sse_response.status_code == 200:
                    print("SSE Events:")
                    for i, line in enumerate(sse_response.iter_lines(decode_unicode=True)):
                        if line:
                            print(f"  [{i}] {line}")
                        if i >= 10:  # Read first 10 events
                            break
                else:
                    print(f"SSE Error: {sse_response.text}")
                    
            except Exception as e:
                print(f"SSE Error: {e}")
                
        else:
            print(f"Scan failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Scan error: {e}")

if __name__ == "__main__":
    test_sse()
    test_scan_and_sse()