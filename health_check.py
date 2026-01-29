#!/usr/bin/env python3
"""
Quick system health check - Verify all components are working
"""
import requests
import json
import sys

def check_system():
    """Check if system is ready"""
    print("\n" + "="*60)
    print("FB AUTO-POSTER - SYSTEM HEALTH CHECK")
    print("="*60 + "\n")
    
    tests = {
        "Server running": "http://localhost:5000",
        "Login page": "http://localhost:5000/login",
        "Dashboard": "http://localhost:5000/dashboard",
        "Groups page": "http://localhost:5000/groups",
        "Post page": "http://localhost:5000/post",
        "Session API": "http://localhost:5000/api/session-status",
    }
    
    passed = 0
    failed = 0
    
    for test_name, url in tests.items():
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200 or response.status_code == 302:
                print(f"✅ {test_name.ljust(25)} - OK (HTTP {response.status_code})")
                passed += 1
            else:
                print(f"⚠️  {test_name.ljust(25)} - Status {response.status_code}")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name.ljust(25)} - Error: {str(e)[:40]}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    if failed == 0:
        print("🎉 ALL SYSTEMS OPERATIONAL - READY FOR PRODUCTION\n")
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - CHECK SERVER STATUS\n")
        return 1

if __name__ == '__main__':
    sys.exit(check_system())
