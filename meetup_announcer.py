import os
import time
import logging
import argparse
import smtplib
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
        # Create message
        msg = MIMEMultipart()
        msg['Subject'] = 'Meetup Announcer Script Error'
        msg['From'] = 'meetup_announcer@gmail.com'  # Replace with your Gmail address
        msg['To'] = 'RuthGraceWong@gmail.com'
        
        # Add error message
        body = f"""
        The Meetup Announcer script encountered an error:
        
        {error_message}
        
        Please check the attached log file and screenshot for details.
        """
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach log file
        with open(log_file_path, 'r') as f:
            log_contents = f.read()
        log_attachment = MIMEText(log_contents)
        log_attachment.add_header('Content-Disposition', 'attachment', filename='meetup_announcer.log')
        msg.attach(log_attachment)
        
        # Attach screenshot if it exists
        if os.path.exists(screenshot_path):
            with open(screenshot_path, 'rb') as f:
                img_data = f.read()
            image = MIMEImage(img_data)
            image.add_header('Content-Disposition', 'attachment', filename='error_screenshot.png')
            msg.attach(image)
        
        # Send email using Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            # Replace 'your_app_password' with the App Password you generate
            server.login(GMAIL_ADDRESS, GMAIL_PASSWORD)
            server.send_message(msg)
        
        logging.info("Error notification email sent successfully")
    except Exception as e:
        logging.error(f"Failed to send error notification email: {str(e)}")

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
    
    # Set Chrome binary location for AlmaLinux
    chrome_options.binary_location = "/usr/lib64/chromium-browser/chromium-browser.sh"
    
    if not manual_login:
        chrome_options.add_argument('--headless=new')  # Use new headless mode
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Add user data directory for persistent profile
    chrome_options.add_argument('--user-data-dir=./chrome_profile')
    
    # Anti-detection options
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    try:
        driver = webdriver.Chrome(options=chrome_options)
        
        # Additional anti-detection measures
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        logging.error(f"Failed to initialize Chrome driver: {str(e)}")
        raise

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
    """Check if event is within the next 18 days."""
    try:
        # Parse the event date string (format: "MON, APR 14, 2025, 3:00 PM PDT")
        event_date = datetime.strptime(event_date_str, "%a, %b %d, %Y, %I:%M %p %Z")
        
        # Get current date
        current_date = datetime.now()
        
        # Calculate date range
        date_range = event_date - current_date
        
        # Check if event is within next 18 days
        return 0 <= date_range.days <= 18
    except Exception as e:
        logging.warning(f"Error parsing date {event_date_str}: {str(e)}")
        return False

def announce_events(driver, group_url):
    """Check and announce events"""
    try:
        # Navigate to group's events page
        events_url = f"{group_url}events/"
        logging.info(f"Attempting to navigate to: {events_url}")
        driver.get(events_url)
        logging.info(f"Successfully navigated to events page: {events_url}")
        
        # Wait for events to load
        logging.info("Waiting for event cards to load...")
        try:
            # Updated selector for event cards
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'a[id^="event-card-e-"]'))
            )
            logging.info("Event cards loaded successfully")
        except TimeoutException:
            logging.error("Timeout waiting for event cards to load")
            # Take a screenshot for debugging
            driver.save_screenshot('error_screenshot.png')
            logging.info("Saved error screenshot to error_screenshot.png")
            raise
        
        processed_events = set()  # Keep track of processed events
        
        while True:
            try:
                # Find all event cards
                event_cards = driver.find_elements(By.CSS_SELECTOR, 'a[id^="event-card-e-"]')
                if not event_cards:
                    logging.info("No more events to process")
                    break
                
                # Find the first unprocessed event
                current_event = None
                for card in event_cards:
                    event_url = card.get_attribute('href')
                    if event_url not in processed_events:
                        current_event = card
                        break
                
                if not current_event:
                    logging.info("All events have been processed")
                    break
                
                # Get event details
                try:
                    date_element = current_event.find_element(By.CSS_SELECTOR, 'time')
                    event_date = date_element.text
                    event_url = current_event.get_attribute('href')
                    
                    # Check if event is within the next 18 days
                    if not is_event_within_range(event_date):
                        logging.info(f"Skipping event on {event_date} - more than 18 days away")
                        processed_events.add(event_url)
                        continue
                    
                    logging.info(f"Processing event on {event_date}")
                    logging.info(f"Navigating to event page: {event_url}")
                except NoSuchElementException as e:
                    logging.warning(f"Could not get event details: {str(e)}")
                    processed_events.add(event_url)  # Mark as processed even if we couldn't get details
                    continue
                
                # Navigate to event page
                driver.get(event_url)
                
                # Wait for the page to load
                time.sleep(2)
                
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
                
                # Mark event as processed
                processed_events.add(event_url)
                
                # Navigate back to events page
                driver.get(events_url)
                time.sleep(2)  # Wait for page to load
                
            except Exception as e:
                logging.error(f"Error processing event: {str(e)}")
                # Take a screenshot for debugging
                try:
                    driver.save_screenshot('error_screenshot.png')
                    logging.info("Saved error screenshot to error_screenshot.png")
                except:
                    logging.error("Could not save error screenshot")
                # Navigate back to events page and continue
                driver.get(events_url)
                time.sleep(2)
                continue
            
    except Exception as e:
        logging.error(f"Error during event announcement: {str(e)}")
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
        driver = setup_driver(args.manual_login)
        
        if args.manual_login:
            if not manual_login(driver, args.group_url):
                return
        
        announce_events(driver, args.group_url)
        
    except Exception as e:
        error_message = f"An error occurred: {e}"
        logging.error(error_message)
        
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