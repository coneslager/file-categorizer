#!/usr/bin/env python3
"""
Debug script to test scanning functionality directly.
"""

import requests
import json
import time
import sys
from pathlib import Path

def test_real_scan():
    """Test scanning with a real directory."""
    base_url = "http://localhost:5000"
    
    # Use the same directory you're testing
    test_dir = r"C:\Users\chris\OneDrive"
    
    print(f"Testing scan of: {test_dir}")
    print("=" * 60)
    
    # Check if directory exists
    if not Path(test_dir).exists():
        print(f"❌ Directory doesn't exist: {test_dir}")
        return False
    
    print(f"✓ Directory exists: {test_dir}")
    
    # 1. Check initial scan status
    try:
        response = requests.get(f"{base_url}/api/scan/status")
        status = response.json()
        print(f"✓ Initial scan status: active={status['active']}")
    except Exception as e:
        print(f"❌ Failed to get initial status: {e}")
        return False
    
    # 2. Start the scan
    try:
        print(f"\n🚀 Starting scan...")
        response = requests.post(f"{base_url}/api/scan", json={
            "path": test_dir,
            "recursive": True,
            "include_hidden": False
        })
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Scan started: {result['message']}")
        else:
            print(f"❌ Scan failed to start: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to start scan: {e}")
        return False
    
    # 3. Monitor scan progress
    print(f"\n📊 Monitoring scan progress...")
    for i in range(30):  # Monitor for 30 seconds
        try:
            response = requests.get(f"{base_url}/api/scan/status")
            status = response.json()
            
            active = status.get('active', False)
            progress = status.get('progress', {})
            
            if not active and i == 0:
                print(f"❌ Scan not active immediately after starting")
                break
            
            if progress:
                total = progress.get('total_files', 0)
                categorized = progress.get('categorized_files', 0)
                scan_status = progress.get('status', 'unknown')
                current_file = progress.get('current_file', '')
                
                print(f"  [{i+1:2d}s] Status: {scan_status}, Files: {categorized}/{total}, Active: {active}")
                if current_file:
                    print(f"       Current: {current_file[:60]}...")
                
                if not active and scan_status in ['completed', 'error', 'cancelled']:
                    print(f"✓ Scan finished with status: {scan_status}")
                    break
            else:
                print(f"  [{i+1:2d}s] No progress data, Active: {active}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error checking status: {e}")
            break
    
    # 4. Final status check
    try:
        response = requests.get(f"{base_url}/api/scan/status")
        final_status = response.json()
        print(f"\n📋 Final status:")
        print(f"   Active: {final_status.get('active', False)}")
        
        progress = final_status.get('progress', {})
        if progress:
            print(f"   Status: {progress.get('status', 'unknown')}")
            print(f"   Total files: {progress.get('total_files', 0)}")
            print(f"   Categorized: {progress.get('categorized_files', 0)}")
            print(f"   New files: {progress.get('new_files', 0)}")
            print(f"   Errors: {len(progress.get('errors', []))}")
            
            if progress.get('errors'):
                print(f"   Error details: {progress['errors'][:3]}")  # Show first 3 errors
        
    except Exception as e:
        print(f"❌ Failed to get final status: {e}")
    
    return True

def test_sse_connection():
    """Test Server-Sent Events connection."""
    print(f"\n🔗 Testing SSE connection...")
    
    try:
        import sseclient  # You might need to install this: pip install sseclient-py
        
        response = requests.get("http://localhost:5000/api/progress/scan", stream=True)
        client = sseclient.SSEClient(response)
        
        print(f"✓ SSE connection established")
        
        # Listen for a few events
        for i, event in enumerate(client.events()):
            if i >= 3:  # Just check first few events
                break
            print(f"  SSE Event: {event.data[:100]}...")
            
    except ImportError:
        print(f"⚠️  SSE client not available (install with: pip install sseclient-py)")
        
        # Fallback: just check if endpoint is accessible
        try:
            response = requests.get("http://localhost:5000/api/progress/scan", timeout=2)
            print(f"✓ SSE endpoint accessible: {response.status_code}")
        except requests.exceptions.Timeout:
            print(f"✓ SSE endpoint accessible (timeout expected)")
        except Exception as e:
            print(f"❌ SSE endpoint error: {e}")
    
    except Exception as e:
        print(f"❌ SSE connection failed: {e}")

if __name__ == "__main__":
    print("File Categorizer Scan Debug Tool")
    print("=" * 60)
    
    if test_real_scan():
        test_sse_connection()
        print(f"\n✅ Debug completed!")
    else:
        print(f"\n❌ Debug failed!")
        sys.exit(1)