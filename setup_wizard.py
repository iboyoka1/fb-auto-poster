"""
Setup Wizard - First-launch configuration and verification
"""
import os
import json
import sys
from configs import PROJECT_ROOT

SETUP_FILE = os.path.join(PROJECT_ROOT, '.setup_complete')
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'setup_config.json')

# Try to import security but don't fail if missing
try:
    from security import password_manager
except ImportError:
    password_manager = None
    print("WARNING: bcrypt not installed, using plaintext passwords")

class SetupWizard:
    """Interactive setup wizard for first launch"""
    
    @staticmethod
    def is_setup_complete():
        """Check if setup has been completed"""
        return os.path.exists(SETUP_FILE)
    
    @staticmethod
    def run_wizard():
        """Run the setup wizard"""
        print("\n" + "="*70)
        print("  FB AUTO-POSTER - FIRST-TIME SETUP WIZARD")
        print("="*70 + "\n")
        
        config = {}
        
        # Step 1: Welcome
        print("👋 Welcome to FB Auto-Poster!\n")
        print("This wizard will help you set up the application for first use.\n")
        input("Press Enter to continue...")
        
        # Step 2: Dashboard password
        print("\n" + "-"*70)
        print("STEP 1: Dashboard Security Setup")
        print("-"*70 + "\n")
        
        print("Set a strong password for your dashboard login.")
        print("(You can also use the default: admin/password123)\n")
        
        use_default = input("Use default credentials? (y/n): ").lower().strip()
        
        if use_default == 'y':
            config['username'] = 'admin'
            if password_manager:
                config['password_hash'] = password_manager.hash_password('password123')
            else:
                config['password_hash'] = 'password123'  # Fallback to plaintext
            print("✓ Using default credentials")
        else:
            username = input("Enter username: ").strip()
            password = input("Enter password: ").strip()
            confirm = input("Confirm password: ").strip()
            
            if password != confirm:
                print("❌ Passwords don't match!")
                return False
            
            if len(password) < 8:
                print("❌ Password must be at least 8 characters!")
                return False
            
            config['username'] = username
            if password_manager:
                config['password_hash'] = password_manager.hash_password(password)
            else:
                config['password_hash'] = password  # Fallback to plaintext
            print(f"✓ Dashboard user '{username}' configured")
        
        # Step 3: System verification
        print("\n" + "-"*70)
        print("STEP 2: System Verification")
        print("-"*70 + "\n")
        
        checks = SetupWizard.verify_system()
        
        if checks['all_good']:
            print("✅ All system checks passed!\n")
        else:
            print("⚠️  Some warnings detected:\n")
            for check, status in checks.items():
                if check != 'all_good' and not status:
                    print(f"  ⚠️  {check}")
            print("\n")
        
        # Step 4: Features
        print("-"*70)
        print("STEP 3: Feature Configuration")
        print("-"*70 + "\n")
        
        config['enable_auto_login'] = input("Enable auto-login support? (y/n): ").lower().strip() == 'y'
        config['enable_email_notifications'] = input("Enable email notifications? (y/n): ").lower().strip() == 'y'
        config['enable_analytics'] = input("Enable analytics tracking? (y/n): ").lower().strip() == 'y'
        
        print("\n✓ Feature configuration complete")
        
        # Step 5: Summary
        print("\n" + "="*70)
        print("SETUP SUMMARY")
        print("="*70 + "\n")
        
        print(f"✓ Dashboard User: {config['username']}")
        print(f"✓ Auto-login: {'Enabled' if config['enable_auto_login'] else 'Disabled'}")
        print(f"✓ Notifications: {'Enabled' if config['enable_email_notifications'] else 'Disabled'}")
        print(f"✓ Analytics: {'Enabled' if config['enable_analytics'] else 'Disabled'}")
        
        confirm = input("\nContinue with this configuration? (y/n): ").lower().strip()
        
        if confirm != 'y':
            print("❌ Setup cancelled")
            return False
        
        # Save configuration
        SetupWizard.save_config(config)
        SetupWizard.mark_setup_complete()
        
        print("\n" + "="*70)
        print("✅ SETUP COMPLETE!")
        print("="*70)
        print("\n🚀 Application will now start...\n")
        
        return True
    
    @staticmethod
    def verify_system():
        """Verify system requirements"""
        checks = {
            'Python version': sys.version_info >= (3, 8),
            'Project directories': SetupWizard.check_directories(),
            'Database access': SetupWizard.check_database(),
            'Network connectivity': SetupWizard.check_network(),
            'all_good': True
        }
        
        for check, status in checks.items():
            if check != 'all_good' and not status:
                checks['all_good'] = False
        
        return checks
    
    @staticmethod
    def check_directories():
        """Check if required directories exist"""
        required = ['sessions', 'media_library', 'logs', 'static', 'templates']
        return all(os.path.isdir(os.path.join(PROJECT_ROOT, d)) for d in required)
    
    @staticmethod
    def check_database():
        """Check database accessibility"""
        try:
            import sqlite3
            db_path = os.path.join(PROJECT_ROOT, 'posts.db')
            conn = sqlite3.connect(db_path)
            conn.close()
            return True
        except:
            return False
    
    @staticmethod
    def check_network():
        """Check network connectivity"""
        try:
            import socket
            socket.create_connection(("1.1.1.1", 53), timeout=2)
            return True
        except:
            return False
    
    @staticmethod
    def save_config(config):
        """Save configuration to file"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except:
            return False
    
    @staticmethod
    def load_config():
        """Load saved configuration"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except:
            pass
        return None
    
    @staticmethod
    def mark_setup_complete():
        """Mark setup as complete"""
        try:
            with open(SETUP_FILE, 'w') as f:
                f.write('setup_complete')
            return True
        except:
            return False
