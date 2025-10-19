#!/usr/bin/env python3
"""
Test UI feedback by monitoring scan status in real-time.
"""

import requests
import time
import threading

def monitor_scan_status():
    """Monitor scan status continuously."""
    print("Monitoring scan status...")
    
    for i in range(20):  # Monitor for 20 seconds
        try:
            response = requests.get("http://localhost:5000/api/scan/status")
            status = response.json()
            
            active = status.get('active', False)
            progress = status.get('progress', {})
            
            if progress:
                scan_status = progress.get('status', 'unknown')
                total = progress.get('total_files', 0)
                categorized = progress.get('categorized_files', 0)
                current_file = progress.get('current_file', '')
                
                print(f"[{i:2d}s] Active: {active}, Status: {scan_status}, Files: {categorized}/{total}")
                if current_file:
                    print(f"      Current: {current_file[:50]}...")
            else:
                print(f"[{i:2d}s] Active: {active}, No progress data")
            
            if not active and i > 0:
                print("Scan finished!")
                break
                
            time.sleep(1)
            
        except Exception as e:
            print(f"[{i:2d}s] Error: {e}")
            time.sleep(1)

def start_test_scan():
    """Start a test scan."""
    print("Starting test scan...")
    
    try:
        response = requests.post("http://localhost:5000/api/scan", json={
            "path": "C:\\Windows\\System32",  # Small directory for testing
            "recursive": False,
            "include_hidden": False
        })
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Scan started: {result['message']}")
            return True
        else:
            print(f"✗ Scan failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"✗ Error starting scan: {e}")
        return False

def test_stop_scan():
    """Test stopping a scan."""
    print("\nTesting stop scan...")
    
    try:
        response = requests.delete("http://localhost:5000/api/scan")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Stop requested: {result['message']}")
        else:
            print(f"✗ Stop failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"✗ Error stopping scan: {e}")

if __name__ == "__main__":
    print("UI Feedback Test")
    print("=" * 50)
    
    # Start monitoring in background
    monitor_thread = threading.Thread(target=monitor_scan_status, daemon=True)
    monitor_thread.start()
    
    # Wait a moment then start scan
    time.sleep(1)
    
    if start_test_scan():
        # Wait a few seconds then try to stop
        time.sleep(3)
        test_stop_scan()
        
        # Wait for monitoring to finish
        monitor_thread.join(timeout=25)
    
    print("\nTest completed!")