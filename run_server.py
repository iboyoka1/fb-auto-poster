#!/usr/bin/env python3
"""
FB GROUP AUTO-POSTER - Server Launcher
Fast, clean, production-ready launcher with setup wizard
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Check if setup is needed
try:
    from setup_wizard import SetupWizard
    
    if not SetupWizard.is_setup_complete():
        print("\n" + "="*50)
        print("First-time setup required!")
        print("="*50)
        
        try:
            if not SetupWizard.run_wizard():
                print("\n❌ Setup failed. Exiting...")
                sys.exit(1)
        except Exception as e:
            print(f"\n⚠️  Setup error (continuing with defaults): {e}")
except Exception as e:
    print(f"Setup check error: {e}")
    print("Continuing with default configuration...")


from app import app

if __name__ == '__main__':
    print("\n" + "="*50)
    print("=" * 50)
    print("  FB GROUP AUTO-POSTER - SERVER")
    print("=" * 50)
    print("=" * 50)
    print("\n[+] Server starting...")
    print("[+] Security: Enabled (bcrypt, JWT, encryption)")
    print("[+] Login system: Enhanced (saves after login)")
    print("[+] Auto group discovery: Enabled")
    print("\n[*] Access at: http://localhost:5000")
    print("[*] Username: admin")
    print("[*] Password: password123")
    print("\n" + "="*50)
    print("=" * 50 + "\n")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
