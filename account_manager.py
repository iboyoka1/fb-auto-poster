"""
Multi-Account Manager for Facebook Auto-Poster
Manage multiple Facebook accounts and switch between them
"""
import json
import os
from typing import List, Dict, Optional
from configs import PROJECT_ROOT


class AccountManager:
    def __init__(self):
        self.accounts_file = f"{PROJECT_ROOT}/accounts.json"
        self.accounts = self.load_accounts()
    
    def load_accounts(self) -> List[Dict]:
        """Load saved accounts"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"[-] Error loading accounts: {e}")
            return []
    
    def save_accounts(self) -> bool:
        """Save accounts to file"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(self.accounts, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[-] Error saving accounts: {e}")
            return False
    
    def add_account(self, name: str, email: str, password: str = None, 
                   cookie_file: str = None) -> Dict:
        """
        Add a new Facebook account
        
        Args:
            name: Account display name
            email: Facebook email/phone
            password: Optional password (for auto-login)
            cookie_file: Optional custom cookie file path
        """
        # Generate cookie file name
        if not cookie_file:
            safe_name = name.replace(' ', '_').lower()
            cookie_file = f"facebook-cookies-{safe_name}.json"
        
        account = {
            'id': len(self.accounts) + 1,
            'name': name,
            'email': email,
            'password': password if password else None,
            'cookie_file': cookie_file,
            'is_active': False,
            'created_at': None  # Will be set when first logged in
        }
        
        self.accounts.append(account)
        self.save_accounts()
        
        return {'success': True, 'account': account}
    
    def get_account(self, account_id: int) -> Optional[Dict]:
        """Get account by ID"""
        for account in self.accounts:
            if account['id'] == account_id:
                return account
        return None
    
    def get_active_account(self) -> Optional[Dict]:
        """Get currently active account"""
        for account in self.accounts:
            if account.get('is_active', False):
                return account
        return None
    
    def set_active_account(self, account_id: int) -> bool:
        """Set an account as active (and deactivate others)"""
        found = False
        for account in self.accounts:
            if account['id'] == account_id:
                account['is_active'] = True
                found = True
            else:
                account['is_active'] = False
        
        if found:
            self.save_accounts()
            # Update the main cookie file symlink
            self._update_active_cookies(account_id)
        return found
    
    def _update_active_cookies(self, account_id: int):
        """Update the main cookie file to point to active account's cookies"""
        account = self.get_account(account_id)
        if not account:
            return False
        
        source = f"{PROJECT_ROOT}/sessions/{account['cookie_file']}"
        target = f"{PROJECT_ROOT}/sessions/facebook-cookies.json"
        
        try:
            # Copy cookies from account-specific file to main file
            if os.path.exists(source):
                import shutil
                shutil.copy2(source, target)
                print(f"[+] Switched to account: {account['name']}")
                return True
            else:
                print(f"[-] Cookie file not found for {account['name']}")
                return False
        except Exception as e:
            print(f"[-] Error switching accounts: {e}")
            return False
    
    def delete_account(self, account_id: int) -> bool:
        """Delete an account"""
        original_len = len(self.accounts)
        account = self.get_account(account_id)
        
        if account:
            # Delete cookie file
            cookie_path = f"{PROJECT_ROOT}/sessions/{account['cookie_file']}"
            if os.path.exists(cookie_path):
                try:
                    os.remove(cookie_path)
                except:
                    pass
        
        self.accounts = [a for a in self.accounts if a['id'] != account_id]
        
        if len(self.accounts) < original_len:
            self.save_accounts()
            return True
        return False
    
    def list_accounts(self) -> List[Dict]:
        """List all accounts"""
        return self.accounts
    
    def account_has_cookies(self, account_id: int) -> bool:
        """Check if account has saved cookies"""
        account = self.get_account(account_id)
        if not account:
            return False
        
        cookie_path = f"{PROJECT_ROOT}/sessions/{account['cookie_file']}"
        return os.path.exists(cookie_path)
    
    def login_account(self, account_id: int, auto_login: bool = True) -> Dict:
        """
        Login to a specific account
        
        Args:
            account_id: Account ID to login
            auto_login: Use automatic login if password available
        """
        account = self.get_account(account_id)
        if not account:
            return {'success': False, 'error': 'Account not found'}
        
        try:
            from main import FacebookGroupSpam
            
            poster = FacebookGroupSpam(headless=True)
            poster.start_browser()
            
            success = False
            
            if auto_login and account.get('password'):
                # Auto-login with credentials
                print(f"[*] Auto-logging into: {account['name']}")
                success = poster.auto_login_with_credentials(
                    account['email'], 
                    account['password']
                )
            else:
                # Manual login
                print(f"[*] Please login manually for: {account['name']}")
                poster.page.goto("https://www.facebook.com")
                input("Press ENTER after you've logged in: ")
                success = True
            
            if success:
                # Save cookies to account-specific file
                cookies = poster.page.context.cookies()
                cookie_path = f"{PROJECT_ROOT}/sessions/{account['cookie_file']}"
                os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
                
                with open(cookie_path, 'w', encoding='utf-8') as f:
                    json.dump(cookies, f, indent=2)
                
                # Set as active account
                self.set_active_account(account_id)
                
                print(f"[+] Successfully logged into: {account['name']}")
            
            poster.close_browser()
            
            return {'success': success, 'account': account}
        
        except Exception as e:
            return {'success': False, 'error': str(e)}


def main():
    """CLI interface for account manager"""
    manager = AccountManager()
    
    print("="*60)
    print("FACEBOOK MULTI-ACCOUNT MANAGER")
    print("="*60)
    print()
    print("1. List accounts")
    print("2. Add account")
    print("3. Login to account")
    print("4. Switch active account")
    print("5. Delete account")
    print()
    
    choice = input("Select option (1-5): ").strip()
    
    if choice == "1":
        accounts = manager.list_accounts()
        if not accounts:
            print("\nNo accounts configured.")
        else:
            print(f"\n{'ID':<5} {'Name':<20} {'Email':<30} {'Active':<10} {'Cookies':<10}")
            print("-"*80)
            for acc in accounts:
                is_active = "\u2713" if acc.get('is_active') else ""
                has_cookies = "\u2713" if manager.account_has_cookies(acc['id']) else ""
                print(f"{acc['id']:<5} {acc['name']:<20} {acc['email']:<30} {is_active:<10} {has_cookies:<10}")
    
    elif choice == "2":
        name = input("\nAccount name: ").strip()
        email = input("Facebook email/phone: ").strip()
        password = input("Password (optional, for auto-login): ").strip() or None
        
        result = manager.add_account(name, email, password)
        if result['success']:
            print(f"\n[+] Account added: {name}")
            print("[*] Use option 3 to login to this account")
    
    elif choice == "3":
        accounts = manager.list_accounts()
        if not accounts:
            print("\nNo accounts configured. Add one first.")
        else:
            for acc in accounts:
                print(f"{acc['id']}. {acc['name']} ({acc['email']})")
            
            acc_id = int(input("\nSelect account ID to login: ").strip())
            auto = input("Use auto-login? (y/n): ").lower() == 'y'
            
            result = manager.login_account(acc_id, auto_login=auto)
            if result['success']:
                print(f"\n[+] Successfully logged in!")
            else:
                print(f"\n[-] Login failed: {result.get('error')}")
    
    elif choice == "4":
        accounts = manager.list_accounts()
        if not accounts:
            print("\nNo accounts configured.")
        else:
            for acc in accounts:
                active = " (ACTIVE)" if acc.get('is_active') else ""
                print(f"{acc['id']}. {acc['name']}{active}")
            
            acc_id = int(input("\nSelect account ID to activate: ").strip())
            if manager.set_active_account(acc_id):
                print(f"\n[+] Account switched!")
            else:
                print(f"\n[-] Failed to switch account")
    
    elif choice == "5":
        accounts = manager.list_accounts()
        if not accounts:
            print("\nNo accounts configured.")
        else:
            for acc in accounts:
                print(f"{acc['id']}. {acc['name']} ({acc['email']})")
            
            acc_id = int(input("\nSelect account ID to delete: ").strip())
            confirm = input(f"Are you sure? (yes/no): ").lower()
            
            if confirm == 'yes':
                if manager.delete_account(acc_id):
                    print(f"\n[+] Account deleted")
                else:
                    print(f"\n[-] Failed to delete account")
    
    print()
    input("Press ENTER to exit...")


if __name__ == "__main__":
    main()
