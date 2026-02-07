from playwright.sync_api import sync_playwright, TimeoutError
import os
import json
import time
import logging

logger = logging.getLogger('fb_auto_poster.main')

# Persistent browser profile directory
BROWSER_PROFILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'browser_profile')

class FacebookGroupSpam:
    def __init__(self, post_content=None, headless=True, media_files=None, use_persistent=True):
        self.post_content = post_content
        self.headless = headless
        self.media_files = media_files
        self.use_persistent = use_persistent  # Use persistent browser profile
        self.browser = None
        self.context = None
        self.page = None
        self.console_messages = []

    def start_browser(self):
        self.playwright = sync_playwright().start()
        
        # Ensure profile directory exists
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
        
        # Use stable browser args for headless Docker environments
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-extensions',
        ]
        
        if self.headless:
            browser_args.append('--headless=new')  # New headless mode for better compatibility
        
        # Context options
        context_options = {
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'viewport': {'width': 1280, 'height': 720},
            'ignore_https_errors': True,
            'locale': 'fr-FR',  # French locale for consistency
            'timezone_id': 'Europe/Paris',
            'permissions': ['geolocation'],
            'java_script_enabled': True,
        }
        
        # Use persistent context to remember login session
        if self.use_persistent:
            try:
                # Check if profile is locked (another browser using it)
                lock_file = os.path.join(BROWSER_PROFILE_DIR, 'SingletonLock')
                if os.path.exists(lock_file):
                    logger.warning("Browser profile is locked, trying to clean up...")
                    try:
                        os.remove(lock_file)
                    except:
                        pass
                
                logger.info(f"Using persistent browser profile: {BROWSER_PROFILE_DIR}")
                self.context = self.playwright.chromium.launch_persistent_context(
                    BROWSER_PROFILE_DIR,
                    headless=self.headless,
                    args=browser_args,
                    slow_mo=50,
                    **context_options
                )
                self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
                logger.info("Using persistent Chromium browser context")
            except Exception as e:
                logger.warning(f"Persistent context failed, falling back to regular context: {e}")
                self.use_persistent = False
        
        if not self.use_persistent:
            # Fallback: Use regular browser context
            try:
                self.browser = self.playwright.chromium.launch(
                    headless=self.headless,
                    args=browser_args,
                    slow_mo=50
                )
                logger.info("Using Chromium browser")
            except Exception as e:
                logger.warning(f"Chromium failed, trying Firefox: {e}")
                try:
                    self.browser = self.playwright.firefox.launch(
                        headless=self.headless,
                        slow_mo=50
                    )
                    logger.info("Using Firefox browser")
                except Exception as e2:
                    logger.error(f"Both browsers failed: Chromium={e}, Firefox={e2}")
                    raise Exception(f"Could not start any browser: {e2}")
            
            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
        
        # Add stealth scripts to avoid bot detection
        self.page.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en']
            });
            
            // Remove automation-related properties
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        logger.info("Browser started successfully with persistent profile")

    def close_browser(self):
        try:
            if self.context:
                self.context.close()
                logger.info("Browser context closed (session saved to persistent profile)")
        except Exception as e:
            logger.warning(f"Error closing browser context: {e}")
        try:
            if hasattr(self, 'playwright'):
                self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")

    def auto_login_with_credentials(self, email, password, timeout: int = 30):
        """Attempt to auto-login using multiple strategies and wait for login cookies.

        Returns True if login cookies (c_user & xs) are present after attempt, else False.
        """
        try:
            logger.info("Starting auto-login attempt")
            # Debug helper to capture screenshot, HTML and console logs
            debug_dir = os.path.join('logs', 'playwright')
            try:
                os.makedirs(debug_dir, exist_ok=True)
            except Exception:
                pass
            def save_debug(name):
                ts = int(time.time())
                try:
                    screenshot_path = os.path.join(debug_dir, f"{name}-{ts}.png")
                    html_path = os.path.join(debug_dir, f"{name}-{ts}.html")
                    console_path = os.path.join(debug_dir, f"{name}-{ts}-console.log")
                    try:
                        if self.page:
                            self.page.screenshot(path=screenshot_path, full_page=True)
                    except Exception as e:
                        logger.debug(f"Screenshot failed: {e}")
                    try:
                        if self.page:
                            with open(html_path, 'w', encoding='utf-8') as fh:
                                fh.write(self.page.content())
                    except Exception as e:
                        logger.debug(f"Dump HTML failed: {e}")
                    try:
                        with open(console_path, 'w', encoding='utf-8') as ch:
                            ch.write("\n".join(getattr(self, 'console_messages', [])))
                    except Exception as e:
                        logger.debug(f"Write console failed: {e}")
                    logger.info(f"Saved debug artifacts: {screenshot_path}, {html_path}, {console_path}")
                except Exception as e:
                    logger.debug(f"save_debug failed: {e}")

            # Try mobile login first - sometimes simpler layout
            targets = [
                'https://m.facebook.com/login',
                'https://www.facebook.com/login',
                'https://www.facebook.com/'
            ]

            for url in targets:
                try:
                    self.page.goto(url, timeout=15000)
                    logger.info(f"Navigated to {url}")
                    break
                except Exception as e:
                    logger.debug(f"Navigation to {url} failed: {e}")
            else:
                logger.error("Failed to navigate to Facebook login pages")
                return False

            # Clear any existing cookies to avoid stale session interference
            try:
                self.context.clear_cookies()
            except Exception:
                pass

            # Wait for typical input selectors (desktop and mobile variants)
            email_selectors = [
                'input[name=login]', 'input[name=email]', '#email', 'input[type=email]', 'input[id=m_login_email]', 'input[name=username]'
            ]
            password_selectors = [
                'input[name=pass]', '#pass', 'input[type=password]', 'input[id=m_login_password]'
            ]

            # Fill email
            filled_email = False
            for sel in email_selectors:
                try:
                    if self.page.query_selector(sel):
                        self.page.fill(sel, email)
                        logger.info(f"Filled email using selector {sel}")
                        filled_email = True
                        break
                except Exception:
                    continue

            # Fill password
            filled_pass = False
            for sel in password_selectors:
                try:
                    if self.page.query_selector(sel):
                        self.page.fill(sel, password)
                        logger.info(f"Filled password using selector {sel}")
                        filled_pass = True
                        break
                except Exception:
                    continue

            if not (filled_email and filled_pass):
                logger.warning('Could not find email or password fields using known selectors')


            # Try to click primary login button
            btn_selectors = ['button[name=login]', 'button[type=submit]', 'input[type=submit]', 'button#loginbutton', 'button[type=button]']
            clicked = False
            for b in btn_selectors:
                try:
                    el = self.page.query_selector(b)
                    if el:
                        try:
                            el.click()
                        except Exception:
                            self.page.click(b)
                        logger.info(f"Clicked login button {b}")
                        clicked = True
                        break
                except Exception as e:
                    logger.debug(f"Click attempt failed for {b}: {e}")
                    continue

            if not clicked:
                # Fallback: press Enter in password field
                try:
                    self.page.keyboard.press('Enter')
                    logger.info("Pressed Enter to submit login form")
                except Exception as e:
                    logger.error(f"Failed to submit login form: {e}")

            # Wait and poll for login cookies - check all Facebook domains
            start = time.time()
            while time.time() - start < timeout:
                try:
                    cookies = self.context.cookies(['https://www.facebook.com', 'https://facebook.com', 'https://m.facebook.com'])
                    names = {c.get('name') for c in cookies}
                    logger.info(f"Checking cookies: {names}")
                    if 'c_user' in names and 'xs' in names:
                        logger.info("Detected login cookies (c_user & xs) - LOGIN SUCCESSFUL!")
                        return True
                except Exception as e:
                    logger.debug(f"Error reading cookies: {e}")
                time.sleep(1)

            try:
                save_debug('auto-login-timeout')
            except Exception:
                pass
            logger.info("Auto-login timed out without detecting cookies")
            return False
        except Exception as e:
            try:
                save_debug('auto-login-exception')
            except Exception:
                pass
            logger.error(f"Auto-Login Error: {e}")
            return False

    def generate_cookie(self, cookie_path):
        cookies = self.context.cookies()
        with open(cookie_path, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2)

    def load_cookie(self, cookie_path=None):
        if not cookie_path:
            # Use absolute path based on script location
            script_dir = os.path.dirname(os.path.abspath(__file__))
            cookie_path = os.path.join(script_dir, 'sessions', 'facebook-cookies.json')
        logger.info(f"Loading cookies from: {cookie_path}")
        if os.path.exists(cookie_path):
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # Sanitize cookies for Playwright compatibility
            sanitized_cookies = []
            for cookie in cookies:
                # Create a copy to avoid modifying original
                c = dict(cookie)
                
                # Fix sameSite value - Playwright expects exactly "Strict", "Lax", or "None"
                same_site = str(c.get('sameSite', '')).lower().strip()
                if same_site == 'strict':
                    c['sameSite'] = 'Strict'
                elif same_site == 'lax':
                    c['sameSite'] = 'Lax'
                elif same_site in ('none', 'no_restriction', 'unspecified', ''):
                    c['sameSite'] = 'None'
                else:
                    # Remove invalid sameSite rather than setting a default
                    c.pop('sameSite', None)
                
                # Ensure domain is set correctly for Facebook
                if 'domain' not in c or not c['domain']:
                    c['domain'] = '.facebook.com'
                
                # Remove any fields that Playwright doesn't accept
                allowed_fields = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'}
                c = {k: v for k, v in c.items() if k in allowed_fields and v is not None}
                
                sanitized_cookies.append(c)
            
            logger.info(f"Loading {len(sanitized_cookies)} cookies into browser context")
            self.context.add_cookies(sanitized_cookies)
            
            # Verify cookies were loaded by checking context cookies
            loaded = self.context.cookies(['https://www.facebook.com'])
            loaded_names = {c.get('name') for c in loaded}
            logger.info(f"Verified loaded cookies: {loaded_names}")
            
            # Warm up session by visiting Facebook main page first
            logger.info("=== WARMING UP FACEBOOK SESSION ===")
            try:
                self.page.goto('https://www.facebook.com/', timeout=30000)
                self.page.wait_for_load_state('domcontentloaded', timeout=15000)
                time.sleep(3)
                
                # Handle "Continue as [Name]" popup if it appears
                self._handle_continue_popup()
                
                current_url = self.page.url
                page_title = self.page.title()
                logger.info(f"Warmup complete - URL: {current_url}")
                logger.info(f"Warmup complete - Title: {page_title}")
                
                # Check if we're logged in - multiple indicators
                # 1. URL contains login
                # 2. Page title indicates login page (multiple languages)
                login_titles = ['connexion', 'inscription', 'log in', 'sign up', 'login', 'تسجيل الدخول']
                title_lower = page_title.lower()
                is_login_page = (
                    'login' in current_url.lower() or 
                    '/login' in current_url or
                    any(lt in title_lower for lt in login_titles)
                )
                
                if is_login_page:
                    logger.warning("⚠️ SESSION EXPIRED - Facebook showing login page. Please upload fresh cookies!")
                    logger.warning(f"Title indicates login: {page_title}")
                else:
                    logger.info("✓ Session warmup: Successfully loaded Facebook (logged in)")
            except Exception as e:
                logger.warning(f"Session warmup failed: {e}")
        else:
            logger.error(f"Cookie file not found: {cookie_path}")

    def _handle_continue_popup(self):
        """Handle Facebook's 'Continue as [Name]' popup that appears after loading cookies"""
        try:
            logger.info("Checking for 'Continue as' popup...")
            
            # Multiple selectors for the "Continue" button in different languages
            continue_selectors = [
                # English
                'div[role="button"]:has-text("Continue")',
                'button:has-text("Continue")',
                '[aria-label*="Continue"]',
                # French
                'div[role="button"]:has-text("Continuer")',
                'button:has-text("Continuer")',
                '[aria-label*="Continuer"]',
                # Arabic
                'div[role="button"]:has-text("متابعة")',
                'button:has-text("متابعة")',
                # Generic - look for button with user name
                'div[role="dialog"] div[role="button"]',
                'div[role="dialog"] button',
                # "Continue as X" pattern
                'div[role="button"][aria-label*="Continue as"]',
                'div[role="button"][aria-label*="Continuer en tant que"]',
            ]
            
            for selector in continue_selectors:
                try:
                    el = self.page.locator(selector).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        logger.info(f"✓ Clicked 'Continue' popup via: {selector}")
                        time.sleep(3)  # Wait for page to reload after clicking
                        return True
                except:
                    continue
            
            logger.info("No 'Continue as' popup found (or already dismissed)")
            return False
            
        except Exception as e:
            logger.debug(f"Continue popup handler error: {e}")
            return False

    def post_to_groups(self, groups, progress_callback=None, should_cancel=None):
        """Post content to multiple Facebook groups using Playwright."""
        results = []
        
        for idx, group in enumerate(groups):
            # Check if posting should be cancelled
            if should_cancel and should_cancel():
                logger.info("Posting cancelled by user")
                break
            
            group_id = group.get('username', '')
            group_name = group.get('name', f'Group {group_id}')
            start_time = time.time()
            
            result = {
                'name': group_name,
                'username': group_id,
                'success': False,
                'error': None
            }
            
            try:
                logger.info(f"Posting to group: {group_name} (ID: {group_id})")
                
                # Navigate to group - use discussion page URL to avoid /about redirect
                group_url = f"https://www.facebook.com/groups/{group_id}"
                self.page.goto(group_url, timeout=120000)  # 2 minutes timeout
                self.page.wait_for_load_state('networkidle', timeout=60000)
                
                # Handle "Continue as [Name]" popup if it appears
                self._handle_continue_popup()
                
                # Wait for dynamic content to fully load
                time.sleep(3)
                
                current_url = self.page.url
                logger.info(f"Current URL after load: {current_url}")
                
                # Check if redirected to /about page - need to go to discussion instead
                if '/about' in current_url or '/about/' in current_url:
                    logger.warning(f"Redirected to /about page, navigating to discussion page...")
                    # Navigate directly to discussion/feed
                    discussion_url = f"https://www.facebook.com/groups/{group_id}/"
                    self.page.goto(discussion_url, timeout=60000)
                    self.page.wait_for_load_state('networkidle', timeout=30000)
                    time.sleep(3)
                    current_url = self.page.url
                    logger.info(f"After redirect fix: {current_url}")
                    
                    # If still on /about, try clicking "Discussion" tab
                    if '/about' in current_url:
                        try:
                            # Try clicking Discussion tab
                            discussion_tab = self.page.locator('a[href*="/discussion"], [role="tab"]:has-text("Discussion"), span:has-text("Discussion")').first
                            if discussion_tab.is_visible(timeout=3000):
                                discussion_tab.click()
                                time.sleep(3)
                                logger.info("Clicked Discussion tab")
                        except:
                            pass
                
                # Scroll down a bit to trigger lazy loading, then back up
                self.page.evaluate("window.scrollBy(0, 300)")
                time.sleep(1)
                self.page.evaluate("window.scrollTo(0, 0)")
                time.sleep(3)
                
                current_url = self.page.url
                logger.info(f"Group page loaded: {current_url}")
                
                # Check if redirected to login
                if 'login' in current_url.lower() or '/login' in current_url:
                    result['error'] = 'Not logged in'
                    logger.error(f"Session expired - login required. Redirected to: {current_url}")
                elif 'checkpoint' in current_url.lower():
                    result['error'] = 'Security checkpoint'
                    logger.error(f"Facebook security checkpoint triggered. URL: {current_url}")
                else:
                    try:
                        # Step 1: Find and click the post creation box
                        post_box_clicked = False
                        
                        # Wait for page to fully render and scroll to find composer
                        time.sleep(3)
                        
                        # Scroll down slowly to trigger lazy loading of composer
                        for scroll_pos in [200, 400, 600]:
                            self.page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                            time.sleep(0.5)
                        
                        # Scroll back to top where composer usually is
                        self.page.evaluate("window.scrollTo(0, 0)")
                        time.sleep(2)
                        
                        logger.info("=== ATTEMPTING TO CLICK COMPOSER ===")
                        
                        # Log what's visible on page for debugging
                        try:
                            page_text = self.page.content()[:2000]
                            logger.info(f"Page content preview: {page_text[:500]}...")
                        except:
                            pass
                        
                        # Method 0: Try clicking the GROUP create post area (top of page, not comments)
                        # The group composer is usually in a fixed position near the top
                        if not post_box_clicked:
                            try:
                                # Scroll to top first - composer is always at top
                                self.page.evaluate("window.scrollTo(0, 0)")
                                time.sleep(1)
                                
                                # Look for the GROUP "Create post" container - NOT comment boxes
                                # Group composer usually has specific aria-labels or is in main content area
                                composer_selectors = [
                                    # French group composer - specific to groups
                                    'div[role="main"] span:has-text("Exprimez-vous")',
                                    'div[role="main"] span:has-text("Écrivez quelque chose")',
                                    # English group composer
                                    'div[role="main"] span:has-text("Write something")',
                                    'div[role="main"] span:has-text("What\'s on your mind")',
                                    # Composer box at top (not in feed items)
                                    'div[data-pagelet="GroupInlineComposer"] div[role="button"]',
                                    'div[aria-label*="Create a post"] >> visible=true',
                                    'div[aria-label*="Créer une publication"] >> visible=true',
                                ]
                                for selector in composer_selectors:
                                    try:
                                        el = self.page.locator(selector).first
                                        if el.is_visible(timeout=2000):
                                            el.click()
                                            post_box_clicked = True
                                            logger.info(f"✓ Method 0: Clicked GROUP composer via: {selector}")
                                            time.sleep(2)
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                logger.debug(f"Method 0 failed: {e}")
                        
                        # Method 1: French "Exprimez-vous" in MAIN area (not comments)
                        if not post_box_clicked:
                            try:
                                # Use first visible button with Exprimez that's near top of page
                                el = self.page.locator('div[role="main"] >> div[role="button"]:has-text("Exprimez")').first
                                if el.is_visible(timeout=3000):
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 1: Clicked 'Exprimez' (French) in main area")
                                    time.sleep(2)
                            except Exception as e:
                                logger.debug(f"Method 1 failed: {e}")
                        
                        # Method 2: English "Write" in MAIN area
                        if not post_box_clicked:
                            try:
                                el = self.page.locator('div[role="main"] >> div[role="button"]:has-text("Write")').first
                                if el.is_visible(timeout=3000):
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 2: Clicked 'Write' button in main area")
                                    time.sleep(2)
                            except Exception as e:
                                logger.debug(f"Method 2 failed: {e}")
                        
                        # Method 3: Try Arabic text in MAIN area
                        if not post_box_clicked:
                            try:
                                el = self.page.locator('div[role="main"] >> div[role="button"]:has-text("اكتب")').first
                                if el.is_visible(timeout=3000):
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 3: Clicked composer via Arabic text in main area")
                                    time.sleep(2)
                            except Exception as e:
                                logger.debug(f"Method 3 failed: {e}")
                        
                        # Method 4: French "Écrivez" in MAIN area
                        if not post_box_clicked:
                            try:
                                el = self.page.locator('div[role="main"] >> div[role="button"]:has-text("Écrivez")').first
                                if el.is_visible(timeout=3000):
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 4: Clicked 'Écrivez' (French) in main area")
                                    time.sleep(2)
                            except Exception as e:
                                logger.debug(f"Method 4 failed: {e}")
                        
                        # Method 5: Click the FIRST contenteditable in main area (composer, not comments)
                        if not post_box_clicked:
                            try:
                                # Comments are usually lower on page, composer is first
                                el = self.page.locator('div[role="main"] >> div[contenteditable="true"]').first
                                if el.is_visible(timeout=3000):
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 5: Clicked first contenteditable in main area")
                                    time.sleep(2)
                            except Exception as e:
                                logger.debug(f"Method 5 failed: {e}")
                        
                        # Method 6: Use get_by_placeholder
                        if not post_box_clicked:
                            try:
                                el = self.page.get_by_placeholder("Write something").first
                                if el.is_visible():
                                    el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 6: Clicked via placeholder")
                            except Exception as e:
                                logger.debug(f"Method 6 failed: {e}")
                        
                        # Method 7: Click any textbox role
                        if not post_box_clicked:
                            try:
                                self.page.click('div[role="textbox"]', timeout=5000)
                                post_box_clicked = True
                                logger.info("✓ Method 7: Clicked textbox role")
                            except Exception as e:
                                logger.debug(f"Method 7 failed: {e}")
                        
                        # Method 8: Use get_by_text for "Write something"
                        if not post_box_clicked:
                            try:
                                write_el = self.page.get_by_text("Write something").first
                                if write_el.is_visible():
                                    write_el.click()
                                    post_box_clicked = True
                                    logger.info("✓ Method 8: Clicked 'Write something' text")
                            except Exception as e:
                                logger.debug(f"Method 8 failed: {e}")
                        
                        # Method 9: Click composer pagelet
                        if not post_box_clicked:
                            try:
                                self.page.click('div[data-pagelet*="Composer"], div[data-pagelet*="composer"]', timeout=5000)
                                post_box_clicked = True
                                logger.info("✓ Method 9: Clicked composer pagelet")
                            except Exception as e:
                                logger.debug(f"Method 9 failed: {e}")
                        
                        # Method 10: Click any element with "What's on your mind"
                        if not post_box_clicked:
                            try:
                                self.page.click('div:has-text("What\'s on your mind")', timeout=5000)
                                post_box_clicked = True
                                logger.info("✓ Method 10: Clicked 'What's on your mind'")
                            except Exception as e:
                                logger.debug(f"Method 10 failed: {e}")
                        
                        if not post_box_clicked:
                            result['error'] = 'Could not find post creation area'
                            logger.error(f"Could not find post box in {group_name}")
                            # Save debug screenshot and HTML
                            try:
                                debug_dir = os.path.join('logs', 'playwright')
                                os.makedirs(debug_dir, exist_ok=True)
                                timestamp = int(time.time())
                                debug_path = os.path.join(debug_dir, f'no-composer-{group_id}-{timestamp}.png')
                                self.page.screenshot(path=debug_path)
                                logger.info(f"Debug screenshot saved: {debug_path}")
                                # Also save HTML for analysis
                                html_path = os.path.join(debug_dir, f'no-composer-{group_id}-{timestamp}.html')
                                with open(html_path, 'w', encoding='utf-8') as f:
                                    f.write(self.page.content())
                                logger.info(f"Debug HTML saved: {html_path}")
                            except Exception as save_err:
                                logger.error(f"Failed to save debug files: {save_err}")
                        else:
                            # Wait for post dialog to open
                            time.sleep(4)
                            
                            logger.info("=== TYPING CONTENT ===")
                            
                            # Step 2: Type content directly (dialog should have focus)
                            typed = False
                            
                            # Just type - the textbox should be focused
                            try:
                                self.page.keyboard.type(self.post_content, delay=30)
                                typed = True
                                logger.info("✓ Typed content into composer")
                            except Exception as e:
                                logger.debug(f"Direct typing failed: {e}")
                            
                            if not typed:
                                result['error'] = 'Could not type content'
                            else:
                                time.sleep(3)
                                
                                # Step 3: Handle media files if any
                                if self.media_files and len(self.media_files) > 0:
                                    logger.info(f"=== UPLOADING {len(self.media_files)} MEDIA FILES ===")
                                    
                                    media_uploaded = False
                                    
                                    # First, check if file exists
                                    valid_media_files = []
                                    for media_file in self.media_files:
                                        if os.path.exists(media_file):
                                            valid_media_files.append(media_file)
                                            logger.info(f"Media file found: {media_file} ({os.path.getsize(media_file)} bytes)")
                                        else:
                                            logger.warning(f"Media file NOT found: {media_file}")
                                    
                                    if not valid_media_files:
                                        logger.error("No valid media files to upload!")
                                    else:
                                        # Save HTML for debugging before trying
                                        try:
                                            debug_dir = os.path.join('logs', 'playwright')
                                            os.makedirs(debug_dir, exist_ok=True)
                                            html_path = os.path.join(debug_dir, f'before-media-{int(time.time())}.html')
                                            with open(html_path, 'w', encoding='utf-8') as f:
                                                f.write(self.page.content())
                                            logger.info(f"Saved dialog HTML: {html_path}")
                                        except:
                                            pass
                                        
                                        # STRATEGY 1: First, try to find existing file input (sometimes already present)
                                        existing_input = None
                                        try:
                                            inputs = self.page.locator('input[type="file"]').all()
                                            logger.info(f"Found {len(inputs)} existing file inputs")
                                            if inputs:
                                                existing_input = inputs[0]
                                        except:
                                            pass
                                        
                                        # STRATEGY 2: Click Photo/Video button to reveal file input
                                        if not existing_input:
                                            photo_button_selectors = [
                                                # In dialog - toolbar icons (most common)
                                                'div[role="dialog"] div[aria-label="Photo/vidéo"]',
                                                'div[role="dialog"] div[aria-label="Photo/video"]',  
                                                'div[role="dialog"] div[aria-label="Photo/Video"]',
                                                'div[role="dialog"] [aria-label*="Photo"][role="button"]',
                                                'div[role="dialog"] [aria-label*="photo"][role="button"]',
                                                # French
                                                '[aria-label="Photo/vidéo"]',
                                                '[aria-label="Ajouter des photos/vidéos"]',
                                                # English
                                                '[aria-label="Photo/video"]',
                                                '[aria-label="Add Photos/Videos"]',
                                                '[aria-label="Add photos/videos"]',
                                                # Generic - image icon in toolbar
                                                'div[role="dialog"] svg[width="24"]',
                                            ]
                                            
                                            logger.info("Looking for Photo/Video button...")
                                            photo_clicked = False
                                            
                                            for selector in photo_button_selectors:
                                                try:
                                                    element = self.page.locator(selector).first
                                                    if element.is_visible(timeout=2000):
                                                        element.click()
                                                        photo_clicked = True
                                                        logger.info(f"✓ Clicked photo button: {selector}")
                                                        time.sleep(3)  # Wait for file dialog or input to appear
                                                        break
                                                except Exception as e:
                                                    logger.debug(f"Selector failed: {selector}")
                                                    continue
                                            
                                            if not photo_clicked:
                                                logger.warning("Could not click Photo button - trying file inputs directly")
                                        
                                        # Wait a moment for any file inputs to appear
                                        time.sleep(2)
                                        
                                        # Now try to upload files
                                        for media_file in valid_media_files:
                                            file_uploaded = False
                                            abs_path = os.path.abspath(media_file)
                                            logger.info(f"Attempting upload: {abs_path}")
                                            
                                            # Try multiple approaches to find/use file input
                                            approaches = [
                                                # Approach A: Standard file input selectors
                                                ('input[type="file"][accept*="image"]', 'image accept'),
                                                ('input[type="file"][accept*="video"]', 'video accept'),
                                                ('input[type="file"][accept="image/*,video/*"]', 'image+video accept'),
                                                ('input[type="file"][multiple]', 'multiple'),
                                                ('input[type="file"]', 'any file input'),
                                                # Approach B: Form-specific
                                                ('form input[type="file"]', 'form input'),
                                                # Approach C: Hidden inputs
                                                ('input[type="file"][style*="display: none"]', 'hidden input'),
                                                ('input[type="file"][class*="hidden"]', 'class hidden'),
                                            ]
                                            
                                            for selector, desc in approaches:
                                                if file_uploaded:
                                                    break
                                                try:
                                                    inputs = self.page.locator(selector).all()
                                                    logger.info(f"  {desc}: found {len(inputs)} inputs")
                                                    
                                                    for idx, file_input in enumerate(inputs):
                                                        try:
                                                            file_input.set_input_files(abs_path)
                                                            file_uploaded = True
                                                            media_uploaded = True
                                                            logger.info(f"  ✓ SUCCESS via {desc}[{idx}]")
                                                            time.sleep(3)
                                                            break
                                                        except Exception as e:
                                                            logger.debug(f"    Input {idx} failed: {str(e)[:50]}")
                                                            continue
                                                except Exception as e:
                                                    logger.debug(f"  {desc} selector error: {str(e)[:50]}")
                                                    continue
                                            
                                            # STRATEGY 3: Use expect_file_chooser for click-based upload
                                            if not file_uploaded:
                                                logger.info("  Trying file chooser approach...")
                                                try:
                                                    # This handles cases where clicking opens native file dialog
                                                    with self.page.expect_file_chooser(timeout=5000) as fc_info:
                                                        # Try to click any photo/upload related element
                                                        try:
                                                            self.page.locator('[aria-label*="Photo"], [aria-label*="photo"], [data-testid*="photo"]').first.click()
                                                        except:
                                                            # Click the first visible button-like element in dialog if nothing else works
                                                            self.page.locator('div[role="dialog"] div[role="button"]').first.click()
                                                    file_chooser = fc_info.value
                                                    file_chooser.set_files(abs_path)
                                                    file_uploaded = True
                                                    media_uploaded = True
                                                    logger.info(f"  ✓ SUCCESS via file chooser")
                                                    time.sleep(3)
                                                except Exception as e:
                                                    logger.debug(f"  File chooser approach failed: {str(e)[:50]}")
                                            
                                            if not file_uploaded:
                                                logger.error(f"  ✗ FAILED to upload: {os.path.basename(media_file)}")
                                                # Save debug screenshot
                                                try:
                                                    debug_path = os.path.join('logs', 'playwright', f'upload-fail-{int(time.time())}.png')
                                                    self.page.screenshot(path=debug_path)
                                                    logger.info(f"  Debug screenshot: {debug_path}")
                                                except:
                                                    pass
                                        
                                        if media_uploaded:
                                            # Wait for media to process/thumbnail to appear
                                            logger.info("Waiting for media preview to appear...")
                                            time.sleep(5)
                                            
                                            # Verify upload by looking for preview
                                            preview_found = False
                                            preview_selectors = [
                                                'div[role="dialog"] img[src*="blob:"]',
                                                'div[role="dialog"] img[src*="scontent"]',
                                                'div[role="dialog"] video',
                                                'div[role="dialog"] [data-visualcompletion="media-vc-image"]',
                                                'div[role="dialog"] img[alt]',
                                            ]
                                            for sel in preview_selectors:
                                                try:
                                                    if self.page.locator(sel).first.is_visible(timeout=3000):
                                                        logger.info(f"✓ Media preview detected: {sel}")
                                                        preview_found = True
                                                        break
                                                except:
                                                    continue
                                            
                                            if not preview_found:
                                                logger.warning("Could not verify media preview, but upload may have succeeded")
                                            
                                            # Extra wait for processing
                                            time.sleep(3)
                                        else:
                                            logger.warning("⚠️ Could not upload media files - posting text only")
                                        # Save debug screenshot
                                        try:
                                            debug_dir = os.path.join('logs', 'playwright')
                                            os.makedirs(debug_dir, exist_ok=True)
                                            debug_path = os.path.join(debug_dir, f'media-fail-{int(time.time())}.png')
                                            self.page.screenshot(path=debug_path)
                                            logger.info(f"Media upload debug screenshot: {debug_path}")
                                        except:
                                            pass
                                
                                # Step 4: Click Post button
                                posted = False
                                
                                # Method 1: French "Publier" (for French FB)
                                try:
                                    self.page.click('div[aria-label="Publier"]', timeout=5000)
                                    posted = True
                                    logger.info("✓ Clicked 'Publier' button (French)")
                                except:
                                    pass
                                
                                # Method 2: English "Post"
                                if not posted:
                                    try:
                                        self.page.click('div[aria-label="Post"]', timeout=5000)
                                        posted = True
                                        logger.info("✓ Clicked 'Post' button (English)")
                                    except:
                                        pass
                                
                                # Method 3: Get by role (French)
                                if not posted:
                                    try:
                                        self.page.get_by_role("button", name="Publier").click()
                                        posted = True
                                        logger.info("✓ Clicked Publier button (role)")
                                    except:
                                        pass
                                
                                # Method 4: Get by role (English)
                                if not posted:
                                    try:
                                        self.page.get_by_role("button", name="Post").click()
                                        posted = True
                                        logger.info("✓ Clicked Post button (role)")
                                    except:
                                        pass
                                
                                # Method 5: Keyboard shortcut
                                if not posted:
                                    try:
                                        self.page.keyboard.press('Control+Enter')
                                        posted = True
                                        logger.info("Submitted via Ctrl+Enter")
                                    except:
                                        pass
                                
                                if posted:
                                    time.sleep(4)
                                    result['success'] = True
                                    logger.info(f"Successfully posted to {group_name}")
                                else:
                                    result['error'] = 'Could not find Post button'
                                    # Save debug screenshot
                                    try:
                                        debug_path = os.path.join('logs', 'playwright', f'post-fail-{int(time.time())}.png')
                                        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                                        self.page.screenshot(path=debug_path)
                                        logger.info(f"Saved debug screenshot: {debug_path}")
                                    except:
                                        pass
                                        
                    except Exception as e:
                        result['error'] = str(e)
                        logger.error(f"Error posting to {group_name}: {e}")
                        
            except TimeoutError as e:
                result['error'] = f'Timeout: {e}'
                logger.error(f"Timeout for group {group_name}")
            except Exception as e:
                result['error'] = str(e)
                logger.error(f"Error with group {group_name}: {e}")
            
            results.append(result)
            
            # Progress callback
            if progress_callback:
                elapsed = int((time.time() - start_time) * 1000)
                progress_callback({'index': idx, 'result': result, 'elapsed_ms': elapsed})
            
            # Delay between posts
            if idx < len(groups) - 1:
                time.sleep(5)
        
        return results

    def validate_session(self):
        self.page.goto('https://www.facebook.com/', timeout=20000)
        cookies = self.context.cookies()
        # Facebook sets a 'c_user' cookie only when logged in
        for cookie in cookies:
            if cookie.get('name') == 'c_user' and cookie.get('value'):
                return True
        return False
