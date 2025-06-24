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
        
        # Attach log file if it exists
        if os.path.exists(log_file_path):
            logging.info(f"Attaching log file: {log_file_path}")
            with open(log_file_path, 'r') as f:
                log_contents = f.read()
            log_attachment = MIMEText(log_contents)
            log_attachment.add_header('Content-Disposition', 'attachment', filename='meetup_announcer.log')
            msg.attach(log_attachment)
        else:
            logging.warning(f"Log file not found: {log_file_path}")
        
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

def setup_driver():
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
    chrome_options.add_argument('--headless=new')
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
    driver.get(f"{group_url}")
    
    # Wait for user to log in
    print("\nPlease log in manually in the browser window.")
    print("The browser should appear on your local machine through X11 forwarding.")
    input("Press Enter when you have completed the login...")
    
    # Verify login was successful
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="header-profile-menu"]'))
        )
        logging.info("Login successful!")
        return True
    except TimeoutException:
        logging.error("Login verification failed. Please try again.")
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
    try:
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
            logging.error("No event cards found with any selector")
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
        
        # Process each event URL
        for event_url, event_date in event_urls:
            try:
                # Check if event is within the next 18 days or in the past
                if not is_event_within_range(event_date):
                    logging.info(f"Found event on {event_date} - more than 18 days away. Stopping processing as events are in chronological order.")
                    return  # Exit the function since all subsequent events will be further in the future
                
                logging.info(f"Processing event on {event_date}")
                logging.info(f"Navigating to event page: {event_url}")
                
                # Navigate to event page
                driver.get(event_url)
                time.sleep(2)  # Wait for page to load
                
                # Look for the announce banner
                try:
                    logging.info("Looking for announce banner...")
                    announce_banner = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="event-announce-banner"]'))
                    )
                    
                    if announce_banner.is_displayed():
                        logging.info("Found announce banner")
                        
                        # Find and click the announce button in the banner
                        announce_button = announce_banner.find_element(By.CSS_SELECTOR, 'button[date-event-label="announce"]')
                        if announce_button.is_displayed() and announce_button.is_enabled():
                            logging.info(f"Clicking announce button for event on {event_date}")
                            announce_button.click()
                            time.sleep(2)  # Wait for any popups or confirmations
                            
                            # Handle any confirmation dialogs
                            try:
                                confirm_button = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="confirm-button"]'))
                                )
                                confirm_button.click()
                                logging.info("Event announced successfully")
                            except TimeoutException:
                                logging.info("No confirmation dialog found")
                        else:
                            logging.info("Announce button not clickable")
                    else:
                        logging.info("Announce banner not visible")
                except TimeoutException:
                    logging.info("No announce banner found - event may already be announced")
                
            except Exception as e:
                error_traceback = traceback.format_exc()
                logging.error(f"Error processing event: {str(e)}\nTraceback:\n{error_traceback}")
                # Take a screenshot for debugging
                try:
                    driver.save_screenshot('error_screenshot.png')
                    logging.info("Saved error screenshot to error_screenshot.png")
                except:
                    logging.error("Could not save error screenshot")
                continue
            
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
    parser.add_argument('--group-url', required=True, help='URL of your Meetup group')
    args = parser.parse_args()
    
    display = None
    driver = None
    
    try:
        display = setup_display(args.manual_login)
        driver = setup_driver()
        
        if args.manual_login:
            if not manual_login(driver, args.group_url):
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