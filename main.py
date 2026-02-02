from playwright.sync_api import sync_playwright, TimeoutError
import os
import json
import time
import logging

logger = logging.getLogger('fb_auto_poster.main')

class FacebookGroupSpam:
    def __init__(self, post_content=None, headless=True, media_files=None):
        self.post_content = post_content
        self.headless = headless
        self.media_files = media_files
        self.browser = None
        self.context = None
        self.page = None
        self.console_messages = []

    def start_browser(self):
        self.playwright = sync_playwright().start()
        # Use stable browser args for headless Docker environments
        browser_args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-extensions',
            '--headless=new',  # New headless mode for better compatibility
        ]
        
        # Use Chromium first (better Docker/headless support), fall back to Firefox
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

        # Use stable context settings with stealth measures
        self.context = self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True,
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            java_script_enabled=True,
        )
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
                get: () => ['en-US', 'en']
            });
            
            // Remove automation-related properties
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        logger.info("Browser started successfully")

    def close_browser(self):
        try:
            if self.browser:
                self.browser.close()
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
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
            cookie_path = os.path.join('sessions', 'facebook-cookies.json')
        if os.path.exists(cookie_path):
            with open(cookie_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            # Sanitize cookies for Playwright compatibility
            sanitized_cookies = []
            for cookie in cookies:
                # Create a copy to avoid modifying original
                c = dict(cookie)
                
                # Fix sameSite value - Playwright expects "Strict", "Lax", or "None"
                same_site = c.get('sameSite', 'Lax')
                if same_site in ('Strict', 'Lax', 'None'):
                    pass  # Already valid
                elif same_site.lower() == 'strict':
                    c['sameSite'] = 'Strict'
                elif same_site.lower() == 'lax':
                    c['sameSite'] = 'Lax'
                elif same_site.lower() in ('none', 'no_restriction', 'unspecified', ''):
                    c['sameSite'] = 'None'
                else:
                    c['sameSite'] = 'Lax'  # Default to Lax for unknown values
                
                # Ensure domain is set correctly for Facebook
                if 'domain' not in c or not c['domain']:
                    c['domain'] = '.facebook.com'
                
                # Remove any fields that Playwright doesn't accept
                allowed_fields = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'}
                c = {k: v for k, v in c.items() if k in allowed_fields}
                
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
                current_url = self.page.url
                page_title = self.page.title()
                logger.info(f"Warmup complete - URL: {current_url}")
                logger.info(f"Warmup complete - Title: {page_title}")
                
                # Check if we're logged in by looking for login elements
                if 'login' in current_url.lower() or '/login' in current_url:
                    logger.warning("Session warmup: Redirected to login page - cookies may be expired")
                else:
                    logger.info("Session warmup: Successfully loaded Facebook (not on login page)")
            except Exception as e:
                logger.warning(f"Session warmup failed: {e}")

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
                
                # Navigate to group
                group_url = f"https://www.facebook.com/groups/{group_id}"
                self.page.goto(group_url, timeout=120000)  # 2 minutes for Render
                self.page.wait_for_load_state('domcontentloaded', timeout=90000)
                # Wait longer for dynamic content on slow connections (Render)
                time.sleep(10)
                
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
                        
                        # Wait a bit more for composer to be ready
                        time.sleep(2)
                        
                        # Method 1: Click on "Write" text (most reliable locally)
                        if not post_box_clicked:
                            try:
                                self.page.click('div[role="button"]:has-text("Write")', timeout=15000)
                                post_box_clicked = True
                                logger.info("Clicked composer via 'Write' selector")
                            except Exception as e:
                                logger.debug(f"Method 1 failed: {e}")
                        
                        # Method 2: Use get_by_text
                        if not post_box_clicked:
                            try:
                                write_el = self.page.get_by_text("Write something").first
                                if write_el.is_visible():
                                    write_el.click()
                                    post_box_clicked = True
                                    logger.info("Clicked 'Write something' text")
                            except Exception as e:
                                logger.debug(f"Method 2 failed: {e}")
                        
                        # Method 3: Try span with Write
                        if not post_box_clicked:
                            try:
                                self.page.click('span:has-text("Write")', timeout=5000)
                                post_box_clicked = True
                                logger.info("Clicked span with 'Write'")
                            except Exception as e:
                                logger.debug(f"Method 3 failed: {e}")
                        
                        # Method 4: Click by coordinates (composer is usually near top)
                        if not post_box_clicked:
                            try:
                                # Try clicking where composer typically is
                                self.page.click('div[data-pagelet*="Composer"], div[data-pagelet*="composer"]', timeout=5000)
                                post_box_clicked = True
                                logger.info("Clicked composer pagelet")
                            except Exception as e:
                                logger.debug(f"Method 4 failed: {e}")
                        
                        if not post_box_clicked:
                            result['error'] = 'Could not find post creation area'
                            logger.error(f"Could not find post box in {group_name}")
                            # Save debug screenshot
                            try:
                                debug_path = f'/tmp/debug-{group_id}-{int(time.time())}.png'
                                self.page.screenshot(path=debug_path)
                                logger.info(f"Debug screenshot saved: {debug_path}")
                            except:
                                pass
                        else:
                            # Wait for post dialog to open
                            time.sleep(3)
                            
                            # Step 2: Type content directly (dialog should have focus)
                            typed = False
                            
                            # Just type - the textbox should be focused
                            try:
                                self.page.keyboard.type(self.post_content, delay=30)
                                typed = True
                                logger.info("Typed content into composer")
                            except Exception as e:
                                logger.debug(f"Direct typing failed: {e}")
                            
                            if not typed:
                                result['error'] = 'Could not type content'
                            else:
                                time.sleep(2)
                                
                                # Step 3: Handle media files if any
                                if self.media_files:
                                    for media_file in self.media_files:
                                        try:
                                            file_input = self.page.locator('input[type="file"]').first
                                            file_input.set_input_files(media_file)
                                            logger.info(f"Uploaded: {media_file}")
                                            time.sleep(3)
                                        except Exception as e:
                                            logger.warning(f"Media upload failed: {e}")
                                
                                # Step 4: Click Post button
                                posted = False
                                
                                # Method 1: Direct click on aria-label="Post"
                                try:
                                    self.page.click('div[aria-label="Post"]', timeout=5000)
                                    posted = True
                                    logger.info("Clicked Post button (aria-label)")
                                except:
                                    pass
                                
                                # Method 2: Get by role
                                if not posted:
                                    try:
                                        self.page.get_by_role("button", name="Post").click()
                                        posted = True
                                        logger.info("Clicked Post button (role)")
                                    except:
                                        pass
                                
                                # Method 3: Keyboard shortcut
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
