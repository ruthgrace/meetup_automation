import os
import time
import logging
import argparse
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from pyvirtualdisplay import Display
from selenium.webdriver.chrome.options import Options
from constants import GMAIL_ADDRESS, GMAIL_PASSWORD
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import pytz
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meetup_announcer.log', mode='w'),  # 'w' mode overwrites the file
        logging.StreamHandler()
    ]
)

def send_error_email(error_message, log_file_path, screenshot_path):
    """Send error notification email with log contents and screenshot."""
    try:
        logging.info("Attempting to send error notification email...")
        
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = 'Meetup Announcer Script Error'
        msg['From'] = GMAIL_ADDRESS  # Use the actual Gmail address from constants
        msg['To'] = 'RuthGraceWong@gmail.com'
        
        # Add error message
        body = f"""
        The Meetup Announcer script encountered an error:
        
        {error_message}
        
        Please check the attached log file and screenshot for details.
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Extract journalctl logs instead of file logs
        try:
            logging.info("Extracting journalctl logs for meetup-announcer service...")
            import subprocess
            
            # Get last 100 lines of logs for the meetup-announcer service
            journal_cmd = ['journalctl', '-u', 'meetup-announcer.service', '-n', '100', '--no-pager']
            result = subprocess.run(journal_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                log_contents = result.stdout
                logging.info(f"Successfully extracted {len(log_contents.splitlines())} lines from journalctl")
            else:
                # Fallback to general system logs if service-specific logs aren't available
                logging.info("Service logs not found, getting recent system logs...")
                journal_cmd = ['journalctl', '-n', '50', '--no-pager', '--since', '1 hour ago']
                result = subprocess.run(journal_cmd, capture_output=True, text=True, timeout=30)
                log_contents = result.stdout if result.returncode == 0 else "Could not retrieve journalctl logs"
            
            log_attachment = MIMEText(log_contents)
            log_attachment.add_header('Content-Disposition', 'attachment', filename='journalctl_logs.txt')
            msg.attach(log_attachment)
            
        except Exception as e:
            logging.warning(f"Could not extract journalctl logs: {str(e)}")
            # Try to attach file log as fallback
            if os.path.exists(log_file_path):
                logging.info(f"Falling back to log file: {log_file_path}")
                with open(log_file_path, 'r') as f:
                    log_contents = f.read()
                log_attachment = MIMEText(log_contents)
                log_attachment.add_header('Content-Disposition', 'attachment', filename='meetup_announcer.log')
                msg.attach(log_attachment)
            else:
                logging.warning("No logs available to attach")
        
        # Attach screenshot if it exists
        if os.path.exists(screenshot_path):
            logging.info(f"Attaching screenshot: {screenshot_path}")
            with open(screenshot_path, 'rb') as f:
                img_data = f.read()
            image = MIMEImage(img_data)
            image.add_header('Content-Disposition', 'attachment', filename='error_screenshot.png')
            msg.attach(image)
        else:
            logging.info(f"Screenshot not found: {screenshot_path}")
        
        # Send email using Gmail SMTP
        logging.info("Connecting to Gmail SMTP server...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            logging.info("Logging into Gmail...")
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            logging.info("Sending email...")
            server.send_message(msg)
        
        logging.info("Error notification email sent successfully")
        print("ERROR NOTIFICATION EMAIL SENT SUCCESSFULLY")  # Also print to console
        
    except Exception as e:
        email_error_traceback = traceback.format_exc()
        error_msg = f"Failed to send error notification email: {str(e)}\nEmail Error Traceback:\n{email_error_traceback}"
        logging.error(error_msg)
        print(f"FAILED TO SEND EMAIL: {str(e)}")  # Also print to console

def setup_display(manual_login=False):
    """Set up virtual display for browser."""
    if manual_login:
        # When manual_login is True, we need X11 forwarding
        if not os.environ.get('DISPLAY'):
            logging.warning("No DISPLAY environment variable found. Make sure you're using SSH with X11 forwarding (-Y flag)")
            raise Exception("No display available. Please connect with 'ssh -Y' for X11 forwarding")
        logging.info("Using existing X11 display")
        return None
    else:
        # For headless mode, we use virtual display
        display = Display(visible=0, size=(1920, 1080))
        display.start()
        return display

def setup_driver(manual_login=False):
    """Set up and return a configured Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-infobars')
    chrome_options.add_argument('--disable-notifications')
    chrome_options.add_argument('--disable-popup-blocking')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--allow-running-insecure-content')
    chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
    chrome_options.add_argument('--disable-site-isolation-trials')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--disable-background-networking')
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-breakpad')
    chrome_options.add_argument('--disable-component-extensions-with-background-pages')
    chrome_options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
    chrome_options.add_argument('--disable-ipc-flooding-protection')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
    chrome_options.add_argument('--metrics-recording-only')
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--password-store=basic')
    chrome_options.add_argument('--use-mock-keychain')
    chrome_options.add_argument('--force-device-scale-factor=1')
    chrome_options.add_argument('--log-level=3')
    chrome_options.add_argument('--silent')
    
    # Only use headless mode if NOT doing manual login
    if not manual_login:
        chrome_options.add_argument('--headless=new')
        logging.info("Running in headless mode")
    else:
        logging.info("Running in visible mode for manual login")
    
    chrome_options.add_argument('--remote-debugging-port=9222')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    chrome_options.add_argument('--binary=/usr/bin/chromium')
    
    # Set page load strategy to eager to prevent timeouts
    chrome_options.page_load_strategy = 'eager'
    
    # Add experimental options
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Create driver with increased timeouts
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)  # Increase page load timeout to 60 seconds
    driver.implicitly_wait(30)  # Increase implicit wait to 30 seconds
    
    # Set script timeout
    driver.set_script_timeout(60)
    
    return driver

def manual_login(driver, group_url):
    """Handle manual login process"""
    logging.info("Starting manual login process...")
    
    try:
        logging.info(f"Navigating to: {group_url}")
        driver.get(f"{group_url}")
        
        # Wait for page to load
        time.sleep(3)
        
        # Check if navigation was successful
        current_url = driver.current_url
        logging.info(f"Current URL after navigation: {current_url}")
        
        if current_url == "data:," or "data:" in current_url:
            logging.error("Navigation failed - still on blank page")
            logging.info("Attempting to navigate again...")
            
            # Try navigating again
            driver.get("https://www.meetup.com")
            time.sleep(3)
            current_url = driver.current_url
            logging.info(f"Current URL after second attempt: {current_url}")
            
            if current_url == "data:," or "data:" in current_url:
                logging.error("Second navigation attempt failed")
                print("\nERROR: Cannot navigate to Meetup.com")
                print("Please manually navigate to https://www.meetup.com in the browser window")
                print("Then log in with your Google account")
            else:
                logging.info("Second navigation attempt successful")
        else:
            logging.info("Navigation successful")
        
    except Exception as e:
        logging.error(f"Error during navigation: {str(e)}")
        print(f"\nERROR: Navigation failed: {str(e)}")
        print("Please manually navigate to https://www.meetup.com in the browser window")
    
    # Wait for user to log in
    print("\nPlease log in manually in the browser window.")
    print("The browser should appear on your local machine through X11 forwarding.")
    print("If the page didn't load, manually navigate to: https://www.meetup.com")
    print("Make sure you:")
    print("1. Click 'Log in' or 'Sign up'")
    print("2. Choose 'Continue with Google'")
    print("3. Complete the Google authentication")
    print("4. You should see your profile picture/menu in the top right")
    input("Press Enter when you have completed the login...")
    
    # Take a screenshot for debugging
    try:
        driver.save_screenshot('login_verification_screenshot.png')
        logging.info("Saved screenshot for login verification debugging")
    except Exception as e:
        logging.warning(f"Could not save screenshot: {str(e)}")
    
    # Check current URL after login
    current_url = driver.current_url
    logging.info(f"Current URL after login: {current_url}")
    
    # Verify login was successful with multiple selectors
    logging.info("Verifying login was successful...")
    
    # Try multiple selectors for profile menu
    profile_selectors = [
        'button#desktop-profile-menu',                    # The actual profile button ID
        'button[aria-label="Profile menu"]',             # The actual aria-label
        'img[alt*="Photo of"]',                          # The profile image alt text
        'button[aria-label*="Profile"]',                 # Generic profile button
        '[data-testid="header-profile-menu"]',           # Original selector (backup)
        '[data-testid="headerProfileMenu"]',             # Alternative
        '[data-testid="nav-profile"]',                   # Another alternative
        '.header-profile',                               # Class-based
        '[data-testid="header-profile"]',                # Another data-testid
        'img[alt*="profile"]',                           # Generic profile image
        'div[data-testid="header"] img',                 # Header image
        'button[data-testid="header-profile-menu-button"]' # Another backup
    ]
    
    login_successful = False
    for selector in profile_selectors:
        try:
            logging.info(f"Trying profile selector: {selector}")
            element = WebDriverWait(driver, 0.5).until(  # Reduced from 3 seconds to 0.5 seconds
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            if element.is_displayed():
                logging.info(f"Found profile element with selector: {selector}")
                login_successful = True
                break
        except TimeoutException:
            logging.info(f"Profile selector {selector} not found")
            continue
    
    if not login_successful:
        logging.warning("Could not find profile menu elements - checking for other login indicators")
        
        # Check for other login indicators
        other_login_indicators = [
            '[data-testid="header"] button',
            '.header button',
            'nav button',
            'header a[href*="profile"]',
            'header a[href*="account"]'
        ]
        
        for selector in other_login_indicators:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    logging.info(f"Found {len(elements)} elements with selector: {selector}")
                    for i, element in enumerate(elements[:3]):  # Check first 3 elements
                        try:
                            text = element.text.strip()
                            if text:
                                logging.info(f"Element {i} text: '{text}'")
                        except:
                            pass
            except Exception as e:
                logging.info(f"Error checking selector {selector}: {str(e)}")
        
        # Check if we're still on a login page
        if 'login' in current_url.lower() or 'signin' in current_url.lower():
            logging.error("Still on login page - login was not completed")
            print("\nERROR: You are still on the login page.")
            print("Please complete the login process and try again.")
            return False
        else:
            logging.warning("Not on login page but couldn't find profile menu")
            print("\nWARNING: Could not verify login status.")
            print("If you are logged in, the automation should still work.")
            print("Continuing anyway...")
            return True
    
    logging.info("Login verification successful!")
    return True

def automated_login(driver, group_url):
    """Attempt automated login using saved credentials."""
    try:
        logging.info("Attempting automated login...")
        
        # Navigate to Meetup login page
        driver.get("https://www.meetup.com/login/")
        time.sleep(3)
        
        # Look for email input field
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[id="email"]',
            'input[placeholder*="email"]'
        ]
        
        email_input = None
        for selector in email_selectors:
            try:
                email_input = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if email_input.is_displayed():
                    logging.info(f"Found email input with selector: {selector}")
                    break
            except TimeoutException:
                continue
        
        if not email_input:
            logging.error("Could not find email input field")
            return False
        
        # Enter email
        email_input.clear()
        email_input.send_keys(MEETUP_EMAIL)
        logging.info("Entered email address")
        
        # Look for password input field
        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[id="password"]',
            'input[placeholder*="password"]'
        ]
        
        password_input = None
        for selector in password_selectors:
            try:
                password_input = driver.find_element(By.CSS_SELECTOR, selector)
                if password_input.is_displayed():
                    logging.info(f"Found password input with selector: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not password_input:
            logging.error("Could not find password input field")
            return False
        
        # Enter password
        password_input.clear()
        password_input.send_keys(MEETUP_PASSWORD)
        logging.info("Entered password")
        
        # Look for submit button
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:contains("Log in")',
            'button:contains("Sign in")',
            '.login-button'
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                if 'contains' in selector:
                    submit_button = driver.find_element(By.XPATH, f"//button[contains(text(), 'Log in')] | //button[contains(text(), 'Sign in')]")
                else:
                    submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                if submit_button.is_displayed() and submit_button.is_enabled():
                    logging.info(f"Found submit button with selector: {selector}")
                    break
            except NoSuchElementException:
                continue
        
        if not submit_button:
            logging.error("Could not find submit button")
            return False
        
        # Click submit
        submit_button.click()
        logging.info("Clicked login button")
        
        # Wait for login to complete
        time.sleep(5)
        
        # Check if login was successful
        if check_authentication(driver):
            logging.info("Automated login successful!")
            return True
        else:
            logging.error("Automated login failed - authentication check failed")
            return False
        
    except Exception as e:
        logging.error(f"Error during automated login: {str(e)}")
        return False

def check_authentication(driver):
    """Check if the user is properly authenticated."""
    try:
        logging.info("Checking authentication status...")
        
        # Look for elements that indicate we're logged in
        login_indicators = [
            '[data-testid="header-profile-menu"]',  # User profile menu
            '[data-testid="headerProfileMenu"]',    # Alternative profile menu
            'button[aria-label*="Profile"]',         # Profile button
            '.header-profile',                       # Profile section
            '[data-testid="nav-profile"]'            # Navigation profile
        ]
        
        for indicator in login_indicators:
            try:
                element = WebDriverWait(driver, 0.5).until(  # Reduced from 3 seconds to 0.5 seconds
                    EC.presence_of_element_located((By.CSS_SELECTOR, indicator))
                )
                if element.is_displayed():
                    logging.info(f"Found authentication indicator: {indicator}")
                    return True
            except TimeoutException:
                continue
        
        # Check if we're on a login page (indicates not logged in)
        login_page_indicators = [
            'input[type="email"]',
            'input[name="email"]',
            'button[type="submit"]',
            'form[action*="login"]',
            '.login-form',
            'input[placeholder*="email"]'
        ]
        
        for indicator in login_page_indicators:
            try:
                element = driver.find_element(By.CSS_SELECTOR, indicator)
                if element.is_displayed():
                    logging.warning(f"Found login page indicator: {indicator}")
                    return False
            except NoSuchElementException:
                continue
        
        # Check URL for login indicators
        current_url = driver.current_url
        if 'login' in current_url.lower() or 'signin' in current_url.lower():
            logging.warning(f"Current URL indicates login page: {current_url}")
            return False
        
        # If we can't find clear indicators, assume we're not logged in
        logging.warning("Could not find clear authentication indicators - assuming not logged in")
        return False
        
    except Exception as e:
        logging.error(f"Error checking authentication: {str(e)}")
        return False

def check_organizer_permissions(driver, group_url):
    """Check if user has organizer permissions for the group."""
    try:
        logging.info("Checking organizer permissions...")
        
        # Navigate to group page
        driver.get(group_url)
        time.sleep(3)
        
        # Look for the "Manage group" button - this is the most reliable indicator
        manage_group_selectors = [
            '#links-manage-group-toggle',  # ID selector
            'button[data-event-label="manage-group-toggle"]',  # Data attribute
            'button[aria-label="Group management actions"]',  # ARIA label
            'button:contains("Manage group")'  # Text content
        ]
        
        for selector in manage_group_selectors:
            try:
                if 'contains' in selector:
                    # Use XPath for contains
                    element = driver.find_element(By.XPATH, f"//button[contains(text(), 'Manage group')]")
                else:
                    element = driver.find_element(By.CSS_SELECTOR, selector)
                
                if element.is_displayed():
                    logging.info(f"Found 'Manage group' button with selector: {selector}")
                    return True
            except NoSuchElementException:
                continue
        
        logging.warning("No 'Manage group' button found - user may not have organizer permissions")
        return False
        
    except Exception as e:
        logging.error(f"Error checking organizer permissions: {str(e)}")
        return False

def is_event_within_range(event_date_str):
    """Check if event is within the next 18 days or in the past."""
    try:
        logging.info(f"Parsing date: {event_date_str}")
        
        # Handle timezone abbreviations
        tz_map = {
            'PDT': 'America/Los_Angeles',
            'PST': 'America/Los_Angeles',
            'EDT': 'America/New_York',
            'EST': 'America/New_York'
        }
        
        # Replace timezone abbreviation if present
        for tz_abbr, tz_name in tz_map.items():
            if tz_abbr in event_date_str:
                # Replace timezone abbreviation
                cleaned_date_str = event_date_str.replace(tz_abbr, '').strip()
                logging.info(f"Cleaned date string: {cleaned_date_str}")
                
                # Parse without timezone first
                date_obj = date_parser.parse(cleaned_date_str)
                
                # Then apply the timezone
                tz = pytz.timezone(tz_name)
                event_date = tz.localize(date_obj)
                logging.info(f"Applied timezone {tz_name} to date: {event_date}")
                break
        else:
            # If no timezone abbreviation found, use default parser
            event_date = date_parser.parse(event_date_str)
            logging.info(f"Using default parser: {event_date}")
        
        # Get current date in the same timezone
        if event_date.tzinfo:
            current_date = datetime.now(event_date.tzinfo)
        else:
            # If event has no timezone, use UTC
            current_date = datetime.now(pytz.UTC)
            
        logging.info(f"Today's date: {current_date.strftime('%Y-%m-%d %I:%M %p %Z')}")
        
        # Calculate date range
        date_range = event_date - current_date
        logging.info(f"Days until event: {date_range.days}")
        
        # Check if event is within next 18 days or in the past
        return date_range.days <= 18
    except Exception as e:
        logging.error(f"Error parsing date {event_date_str}: {str(e)}")
        # Return True to process the event anyway if we can't parse the date
        return True

def announce_events(driver, group_url):
    """Navigate to events page and announce events."""
    events_processed = 0
    events_announced = 0
    events_failed_to_announce = 0
    failed_events = []
    
    try:
        # First, check if we're authenticated
        if not check_authentication(driver):
            error_message = ("AUTHENTICATION ISSUE: The script is not logged in to Meetup.com. "
                           "This is likely why no announce buttons are being found. "
                           "Please run the script with --manual-login to authenticate:\n\n"
                           "cd /var/www/meetup_automation\n"
                           "source venv/bin/activate\n"
                           "python meetup_announcer.py --manual-login --group-url \"https://www.meetup.com/joyful-parenting-sf/\"\n\n"
                           "Then log in through the browser window that appears.")
            
            logging.error("Authentication check failed - not logged in")
            send_error_email(
                error_message,
                'meetup_announcer.log',
                'authentication_error_screenshot.png'
            )
            
            # Take screenshot for debugging
            try:
                driver.save_screenshot('authentication_error_screenshot.png')
                logging.info("Saved authentication error screenshot")
            except:
                logging.error("Could not save authentication error screenshot")
            
            return
        
        logging.info("Authentication check passed - user appears to be logged in")
        
        # Check organizer permissions
        if not check_organizer_permissions(driver, group_url):
            error_message = ("ORGANIZER PERMISSIONS ISSUE: The logged-in user does not appear to have "
                           "organizer permissions for this Meetup group. Only organizers can announce events. "
                           "Please verify that the logged-in account has organizer access to the group.")
            
            logging.error("Organizer permissions check failed")
            send_error_email(
                error_message,
                'meetup_announcer.log',
                'permissions_error_screenshot.png'
            )
            
            # Take screenshot for debugging
            try:
                driver.save_screenshot('permissions_error_screenshot.png')
                logging.info("Saved permissions error screenshot")
            except:
                logging.error("Could not save permissions error screenshot")
            
            return
        
        logging.info("Organizer permissions check passed")
        
        events_url = f"{group_url}events/"
        logging.info(f"Attempting to navigate to: {events_url}")
        
        # Add retry logic for page load
        max_retries = 3
        for attempt in range(max_retries):
            try:
                driver.get(events_url)
                logging.info(f"Successfully navigated to events page: {events_url}")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logging.warning(f"Attempt {attempt + 1} failed to load page: {str(e)}")
                time.sleep(5)  # Wait before retrying
        
        # Wait for event cards with increased timeout
        logging.info("Waiting for event cards to load...")
        wait = WebDriverWait(driver, 30)  # Increase timeout to 30 seconds
        
        # Try multiple selectors with increased timeouts
        selectors = [
            'a[id^="event-card-e-"]',
            'a[data-event-label^="event-card-"]',
            'a[href*="/events/"]'
        ]
        
        event_cards = None
        for selector in selectors:
            try:
                logging.info(f"Trying selector: {selector}")
                event_cards = wait.until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
                )
                if event_cards:
                    logging.info(f"Found event cards with selector: {selector}")
                    break
            except Exception as e:
                logging.warning(f"Selector {selector} failed: {str(e)}")
                continue
        
        if not event_cards:
            error_msg = "No event cards found with any selector"
            logging.error(error_msg)
            # Since we're authenticated, this might be a website change issue
            send_error_email(
                f"WEBSITE STRUCTURE CHANGE: Could not find event cards on {group_url}events/. "
                f"This might indicate that Meetup.com has changed their website structure. "
                f"Authentication appears to be working correctly.",
                'meetup_announcer.log',
                'no_events_screenshot.png'
            )
            
            # Take screenshot for debugging
            try:
                driver.save_screenshot('no_events_screenshot.png')
                logging.info("Saved no events found screenshot")
            except:
                logging.error("Could not save no events screenshot")
            
            return
        
        logging.info("Event cards loaded successfully")
        
        # Get all event URLs first to avoid stale elements
        event_urls = []
        for card in event_cards:
            try:
                event_url = card.get_attribute('href')
                date_element = card.find_element(By.CSS_SELECTOR, 'time')
                event_date = date_element.text
                event_urls.append((event_url, event_date))
            except Exception as e:
                logging.warning(f"Could not get event details from card: {str(e)}")
                continue
        
        logging.info(f"Found {len(event_urls)} events to process")
        
        # Process each event URL
        for event_url, event_date in event_urls:
            try:
                # Check if event is within the next 18 days or in the past
                if not is_event_within_range(event_date):
                    logging.info(f"Found event on {event_date} - more than 18 days away. Stopping processing as events are in chronological order.")
                    break  # Exit the loop since all subsequent events will be further in the future
                
                events_processed += 1
                logging.info(f"Processing event {events_processed} on {event_date}")
                logging.info(f"Navigating to event page: {event_url}")
                
                # Navigate to event page
                driver.get(event_url)
                time.sleep(3)  # Increased wait time for page to load
                
                # Look for the announce banner with multiple selectors and longer waits
                announce_found = False
                banner_selectors = [
                    '[data-testid="event-announce-banner"]',
                    '.z-banner [data-testid="event-announce-banner"]',
                    'div[data-testid="banner"] [data-testid="event-announce-banner"]',
                    '.bg-tooltipDark [data-testid="event-announce-banner"]'
                ]
                
                for banner_selector in banner_selectors:
                    try:
                        logging.info(f"Looking for announce banner with selector: {banner_selector}")
                        announce_banner = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, banner_selector))
                        )
                        
                        if announce_banner.is_displayed():
                            logging.info(f"Found announce banner with selector: {banner_selector}")
                            announce_found = True
                            
                            # Try multiple button selectors
                            button_selectors = [
                                'button[date-event-label="announce"]',
                                'button[data-event-label="announce"]',
                                'button:contains("Announce")',
                                'button span:contains("Announce")'
                            ]
                            
                            button_clicked = False
                            for button_selector in button_selectors:
                                try:
                                    if 'contains' in button_selector:
                                        # Use XPath for contains
                                        xpath_selector = f"//button[contains(text(), 'Announce')] | //button//span[contains(text(), 'Announce')]/.."
                                        announce_button = announce_banner.find_element(By.XPATH, xpath_selector)
                                    else:
                                        announce_button = announce_banner.find_element(By.CSS_SELECTOR, button_selector)
                                    
                                    if announce_button.is_displayed() and announce_button.is_enabled():
                                        logging.info(f"Found clickable announce button with selector: {button_selector}")
                                        logging.info(f"Clicking announce button for event on {event_date}")
                                        announce_button.click()
                                        button_clicked = True
                                        time.sleep(3)  # Wait for any popups or confirmations
                                        
                                        # Handle any confirmation dialogs
                                        try:
                                            confirm_button = WebDriverWait(driver, 5).until(
                                                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="confirm-button"]'))
                                            )
                                            confirm_button.click()
                                            logging.info("Clicked confirmation button")
                                        except TimeoutException:
                                            logging.info("No confirmation dialog found")
                                        
                                        events_announced += 1
                                        logging.info(f"Event on {event_date} announced successfully!")
                                        break
                                    else:
                                        logging.info(f"Button found but not clickable with selector: {button_selector}")
                                except Exception as e:
                                    logging.warning(f"Button selector {button_selector} failed: {str(e)}")
                                    continue
                            
                            if not button_clicked:
                                logging.warning(f"Found announce banner but could not click button for event on {event_date}")
                                events_failed_to_announce += 1
                                failed_events.append(f"{event_date}: Found banner but button not clickable")
                            
                            break  # Exit banner selector loop since we found the banner
                        else:
                            logging.info(f"Banner found but not visible with selector: {banner_selector}")
                    except TimeoutException:
                        logging.info(f"No announce banner found with selector: {banner_selector}")
                        continue
                
                if not announce_found:
                    logging.info(f"No announce banner found for event on {event_date} - event may already be announced")
                    # Take a screenshot for debugging (but don't send email - this is normal)
                    try:
                        screenshot_path = f'no_banner_screenshot_{event_date.replace("/", "_").replace(" ", "_")}.png'
                        driver.save_screenshot(screenshot_path)
                        logging.info(f"Saved screenshot to {screenshot_path}")
                    except Exception as e:
                        logging.warning(f"Could not save screenshot: {str(e)}")
                
            except Exception as e:
                events_failed_to_announce += 1
                error_traceback = traceback.format_exc()
                error_msg = f"Error processing event on {event_date}: {str(e)}\nTraceback:\n{error_traceback}"
                logging.error(error_msg)
                failed_events.append(f"{event_date}: {str(e)}")
                
                # Take a screenshot for debugging
                try:
                    driver.save_screenshot('error_screenshot.png')
                    logging.info("Saved error screenshot to error_screenshot.png")
                except:
                    logging.error("Could not save error screenshot")
                continue
        
        # Summary logging
        logging.info(f"=== PROCESSING COMPLETE ===")
        logging.info(f"Events processed: {events_processed}")
        logging.info(f"Events announced: {events_announced}")
        logging.info(f"Events failed to announce: {events_failed_to_announce}")
        
        # Send email notification only for actual failures (not when events are already announced)
        if events_failed_to_announce > 0:
            error_message = f"ANNOUNCE FAILURES: Failed to announce {events_failed_to_announce} out of {events_processed} events:\n\n" + "\n".join(failed_events)
            error_message += f"\n\nNote: Events without announce banners are typically already announced and don't require action."
            
            logging.warning("Sending email notification about failed announces")
            send_error_email(
                error_message,
                'meetup_announcer.log',
                'error_screenshot.png'
            )
        elif events_announced > 0:
            logging.info(f"SUCCESS: Announced {events_announced} events - no notification needed")
        else:
            logging.info("NO ACTION NEEDED: No events required announcing - all events may already be announced")
            
    except Exception as e:
        error_traceback = traceback.format_exc() 
        logging.error(f"Error during event announcement: {str(e)}\nTraceback:\n{error_traceback}")
        # Take a screenshot for debugging
        try:
            driver.save_screenshot('error_screenshot.png')
            logging.info("Saved error screenshot to error_screenshot.png")
        except:
            logging.error("Could not save error screenshot")
        raise

def main():
    parser = argparse.ArgumentParser(description='Meetup Event Announcer')
    parser.add_argument('--manual-login', action='store_true', help='Perform manual login')
    parser.add_argument('--auto-login', action='store_true', help='Attempt automated login using saved credentials')
    parser.add_argument('--group-url', required=True, help='URL of your Meetup group')
    args = parser.parse_args()
    
    display = None
    driver = None
    
    try:
        display = setup_display(args.manual_login)
        driver = setup_driver(args.manual_login)  # Pass manual_login parameter
        
        if args.manual_login:
            if not manual_login(driver, args.group_url):
                return
        elif args.auto_login:
            if not automated_login(driver, args.group_url):
                logging.error("Automated login failed. You may need to run with --manual-login instead.")
                return
        
        announce_events(driver, args.group_url)
        
    except Exception as e:
        # Get full traceback for debugging
        full_traceback = traceback.format_exc()
        error_message = f"An error occurred: {e}\nStacktrace:\n{full_traceback}"
        logging.error(error_message)
        print(f"\n=== SCRIPT ERROR OCCURRED ===")
        print(f"Error: {e}")
        print(f"Attempting to send error notification email...")
        
        # Send error notification email
        send_error_email(
            error_message,
            'meetup_announcer.log',
            'error_screenshot.png'
        )
    finally:
        if driver:
            driver.quit()
        if display:
            display.stop()

if __name__ == "__main__":
    main() 