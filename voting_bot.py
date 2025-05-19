import logging
import threading
import time
from faker import Faker
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import schedule
import random
import os

fake = Faker('de_DE')  # German locale for relevant data

# Configure logging with more details and file output
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG for more details
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f"voting-bot-{time.strftime('%Y%m%d-%H%M%S')}.log")),
        logging.StreamHandler()  # This will print to console too
    ]
)

# List of vote targets
SITES = [
    # {"name": "HR4", "url": "https://www.hr4.de/musik/die-ard-schlagerhitparade/abstimmung-zur-hr4-hitparade-v3,hr4-hitparade-abstimmung-100.html"},
    # {"name": "MDR", "url": "https://www.mdr.de/sachsenradio/programm/deutschehitparade106.html"},
    {"name": "SWR", "url": "https://www.swr.de/schlager/voting-abstimmung-ard-schlagerhitparade-136.html"},
]

class VotingBot:
    def __init__(self):
        self.successful_votes = 0
        self.failed_votes = 0
        self.total_attempts = 0
        self.running = True
        # Create screenshot directory
        self.screenshot_dir = "screenshots"
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
        logging.debug("VotingBot initialized")

    def setup_browser(self):
        logging.debug("Setting up browser...")
        options = webdriver.ChromeOptions()
        
        # Uncomment the line below if you want to see the browser (for debugging)
        # options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--allow-file-access-from-files")
        options.add_argument("--disable-notifications")
        options.add_argument("--window-size=1920,1080")  # Set window size
        
        # Add a random user agent to avoid detection
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.55 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
        ]
        selected_agent = random.choice(user_agents)
        options.add_argument(f"user-agent={selected_agent}")
        logging.debug(f"Using user agent: {selected_agent}")

        try:
            logging.debug("Installing ChromeDriver...")
            service = Service(ChromeDriverManager().install())
            logging.debug("Creating Chrome WebDriver instance...")
            driver = webdriver.Chrome(service=service, options=options)
            logging.debug("Browser setup successful")
            return driver
        except Exception as e:
            logging.error(f"Error setting up browser: {e}", exc_info=True)
            return None

    def take_screenshot(self, driver, name):
        """Take a screenshot and save it with a timestamp"""
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = os.path.join(self.screenshot_dir, f"{name}-{timestamp}.png")
        try:
            driver.save_screenshot(filename)
            logging.debug(f"Screenshot saved: {filename}")
            return filename
        except Exception as e:
            logging.error(f"Failed to take screenshot: {e}")
            return None

    def debug_page(self, driver, step_name):
        """Log page title, URL, and take a screenshot"""
        logging.debug(f"--- DEBUG {step_name} ---")
        logging.debug(f"Current URL: {driver.current_url}")
        logging.debug(f"Page title: {driver.title}")
        self.take_screenshot(driver, f"debug-{step_name}")
        
        # Log page source to a file (helpful for debugging HTML elements)
        source_dir = "page_sources"
        if not os.path.exists(source_dir):
            os.makedirs(source_dir)
        
        try:
            source_file = os.path.join(source_dir, f"source-{step_name}-{time.strftime('%Y%m%d-%H%M%S')}.html")
            with open(source_file, 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            logging.debug(f"Page source saved to {source_file}")
        except Exception as e:
            logging.error(f"Failed to save page source: {e}")

    def handle_cookie_consent(self, driver):
        """Handle cookie consent dialogs"""
        try:
            logging.debug("Looking for cookie consent dialog...")
            cookie_selectors = [
                "//button[contains(text(), 'Akzeptieren')]",
                "//button[contains(text(), 'Accept')]",
                "//button[contains(text(), 'OK')]",
                "//button[contains(text(), 'Zustimmen')]",
                "//button[contains(@class, 'accept')]",
                "//button[contains(@class, 'consent')]",
                "//div[contains(@class, 'cookie')]//button",
                "//div[contains(@id, 'cookie')]//button",
                ".cookie-notice button",
                "#cookieConsent button"
            ]
            
            for selector in cookie_selectors:
                try:
                    cookie_button = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH if selector.startswith("//") else By.CSS_SELECTOR, selector))
                    )
                    logging.debug(f"Found cookie button with selector: {selector}")
                    cookie_button.click()
                    logging.debug("Clicked cookie consent button")
                    time.sleep(2)
                    return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logging.debug(f"No cookie dialog found or couldn't interact with it: {e}")
            return False

    def vote_on_hr4(self, driver):
        try:
            print("Accepting cookies if present...")
            try:
                cookie_button = driver.find_element(By.CSS_SELECTOR, "[data-testid='gdpr-accept-all']")
                cookie_button.click()
                time.sleep(1)
            except:
                pass  # Cookie popup not shown

            print("Locating voting checkboxes...")
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='multivoting']")
            if len(checkboxes) < 2:
                raise Exception(f"Expected at least 2 voting checkboxes, found {len(checkboxes)}")

            selected = random.sample(checkboxes, 2)
            for box in selected:
                driver.execute_script("arguments[0].scrollIntoView(true);", box)
                driver.execute_script("arguments[0].click();", box)

            print("Enabling and clicking the submit button...")
            submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Abstimmen']")
            driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(3)  # wait for confirmation to appear

            print("Checking for success message...")
            success_msg = driver.find_elements(By.CSS_SELECTOR, "p.text-success")
            if success_msg:
                print("Vote successful.")
                return True

            page_text = driver.page_source.lower()
            if "danke" in page_text or "ergebnis" in page_text:
                print("Vote likely successful based on page content.")
                return True

            print("Vote may not have been successful.")
            return False

        except Exception as e:
            print(f"Voting failed: {e}")
            return False
        
    def vote_on_mdr(self, driver):
        try:
            self.debug_page(driver, "mdr-initial-load")
            logging.debug("Processing MDR voting page...")

            # self.handle_cookie_consent(driver)
            # self.debug_page(driver, "mdr-after-cookie")

            logging.debug("Looking for MDR voting elements...")

            # Find all visible voting buttons
            try:
                voting_buttons = driver.find_elements(By.CSS_SELECTOR, ".wertungspad button.okaytoggle")
            except Exception:
                self.debug_page(driver, "mdr-options-error")
                raise Exception("Error finding voting buttons")

            if not voting_buttons:
                self.debug_page(driver, "mdr-no-options-found")
                raise Exception("No voting buttons found")

            # Filter visible and clickable buttons
            visible_buttons = [btn for btn in voting_buttons if btn.is_displayed()]
            if not visible_buttons:
                raise Exception("Voting buttons not visible or interactable")

            random_button = random.choice(visible_buttons)

            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", random_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", random_button)
            except Exception:
                raise Exception("Could not click the voting button")

            self.debug_page(driver, "mdr-after-selection")

            # --- ADDED: Fill the form ---
            try:
                # names = ["Anna Schmidt", "Max Mustermann", "Lisa Müller"]
                # addresses = ["Berlin, Germany", "Leipzig, Germany", "Hamburg, Germany"]
                # emails = ["test1@example.com", "test2@example.com", "test3@example.com"]
                # songs = ["Song A", "Song B", "Song C"]

                # driver.find_element(By.NAME, "ff1").send_keys(random.choice(names))
                # driver.find_element(By.NAME, "ff2").send_keys(random.choice(addresses))
                # driver.find_element(By.NAME, "ff3").send_keys(random.choice(emails))
                # driver.find_element(By.NAME, "ff4").send_keys(random.choice(songs))

                # Generate fake data
                name = fake.name()
                address = fake.address().replace('\n', ', ')  # Clean line breaks
                email = fake.email()
                # songs = ["Song A", "Song B", "Song C"]

                # Use Selenium to input data
                driver.find_element(By.NAME, "ff1").send_keys(name)
                driver.find_element(By.NAME, "ff2").send_keys(address)
                driver.find_element(By.NAME, "ff3").send_keys(email)
                # driver.find_element(By.NAME, "ff4").send_keys(random.choice(songs))

                self.debug_page(driver, "mdr-after-form-fill")
            except Exception as e:
                self.debug_page(driver, "mdr-form-fill-error")
                logging.error("Error filling out the MDR form", exc_info=True)
                raise Exception("Form fields not found or not fillable")

            # --- END ADDED ---

            # Submit button 
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, "button[name='Absenden']")
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", submit_button)
            except Exception:
                self.debug_page(driver, "mdr-submit-failed")
                raise Exception("Submit button not clickable")

            self.debug_page(driver, "mdr-after-submit")
            time.sleep(3)

            # Confirmation check: if no buttons remain or a confirmation block appears
            try:
                remaining_buttons = driver.find_elements(By.CSS_SELECTOR, ".wertungspad button.okaytoggle")
                if not remaining_buttons:
                    self.debug_page(driver, "mdr-confirmed")
                    return True
            except Exception:
                pass

            return False

        except Exception as e:
            logging.error(f"Error during MDR voting process: {e}", exc_info=True)
            self.debug_page(driver, "mdr-error")
            return False

    def vote_on_swr(self, driver):
        try:
            print("Locating voting checkboxes on SWR site...")
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='votingitem']")
            if len(checkboxes) < 3:
                raise Exception(f"Expected at least 3 voting checkboxes, found {len(checkboxes)}")

            selected = random.sample(checkboxes, 3)
            for box in selected:
                driver.execute_script("arguments[0].scrollIntoView(true);", box)
                driver.execute_script("arguments[0].click();", box)


             # --- ADDED: Fill the form ---
            try:
                # Generate fake data
                name1 = fake.name()
                name2 = fake.name()
                email = fake.email()
                # Use Selenium to input data
                driver.find_element(By.NAME, "formField_vorname").send_keys(name1)
                driver.find_element(By.NAME, "formField_nachname").send_keys(name2)
                driver.find_element(By.NAME, "formField_email").send_keys(email)
                self.debug_page(driver, "swr-after-form-fill")
            except Exception as e:
                self.debug_page(driver, "mdr-form-fill-error")
                logging.error("Error filling out the swr form", exc_info=True)
                raise Exception("Form fields not found or not fillable")

            checkbox = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='formField_teilnahmebedingungen']")[0]
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            driver.execute_script("arguments[0].click();", checkbox)

            print("Looking for submit button...")
            submit_button = driver.find_element(By.CSS_SELECTOR, "form button[type='submit'], form input[type='submit']")
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(1)

            print("Waiting for manual CAPTCHA (if required)...")
            input("Solve CAPTCHA manually and press Enter to continue...")

            print("Submitting form...")
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(3)  # wait for confirmation

            page_text = driver.page_source.lower()
            if "danke" in page_text or "ihre stimme wurde gezählt" in page_text:
                print("Vote successful.")
                return True

            print("Vote may not have been successful.")
            return False

        except Exception as e:
            print(f"SWR Voting failed: {e}")
            return False

    def vote_on_site(self, site):
        logging.info(f"Starting vote on {site['name']}")
        driver = self.setup_browser()
        if not driver:
            self.failed_votes += 1
            return

        try:
            logging.debug(f"Navigating to {site['url']}")
            driver.get(site["url"])
            logging.debug("Waiting for page to load...")
            time.sleep(5)  # wait longer for the page to load

            if site["name"] == "HR4":
                success = self.vote_on_hr4(driver)
            elif site["name"] == "MDR":
                success = self.vote_on_mdr(driver)
            elif site["name"] == "SWR":
                success = self.vote_on_swr(driver)
            else:
                logging.warning(f"No specific voting logic for site: {site['name']}")
                success = False
                
            if success:
                self.successful_votes += 1
                logging.info(f"Successfully voted on {site['name']}")
            else:
                self.failed_votes += 1
                logging.warning(f"Failed to vote on {site['name']}")
                
        except Exception as e:
            logging.error(f"Failed to vote on {site['name']}: {e}", exc_info=True)
            self.failed_votes += 1
        finally:
            if driver:
                logging.debug("Closing browser")
                driver.quit()

    def vote_all(self):
        self.total_attempts += 1
        logging.info("=============================================")
        logging.info(f"Starting voting cycle #{self.total_attempts}")
        logging.info("=============================================")
        
        for site in SITES:
            self.vote_on_site(site)
        
        logging.info("=============================================")
        logging.info(f"Voting cycle #{self.total_attempts} completed.")
        logging.info(f"Successful votes: {self.successful_votes}/{len(SITES)}")
        logging.info(f"Current stats: {self.get_stats()}")
        logging.info("=============================================")

    def get_stats(self):
        return {
            "total_attempts": self.total_attempts,
            "successful_votes": self.successful_votes,
            "failed_votes": self.failed_votes,
        }

    def start_scheduled_voting(self, interval_minutes=30):
        logging.info(f"Setting up scheduled voting every {interval_minutes} minutes")
        
        # Run once immediately
        self.vote_all()
        
        # Then schedule recurring votes
        schedule.every(interval_minutes).minutes.do(self.vote_all)

        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def stop(self):
        self.running = False
        logging.info("=============================================")
        logging.info("Voting bot stopped by user")
        logging.info(f"Final stats: {self.get_stats()}")
        logging.info("=============================================")

def run_bot():
    logging.info("=============================================")
    logging.info("Starting Voting Bot for HR4 and MDR")
    logging.info("=============================================")
    
    bot = VotingBot()

    # Ask for voting interval
    try:
        interval = int(input("Enter voting interval in minutes (default 30): ") or "30")
    except ValueError:
        interval = 30
        logging.info("Invalid input, using default 30 minutes")

    logging.info(f"Starting bot with {interval} minute intervals")
    
    voting_thread = threading.Thread(target=bot.start_scheduled_voting, args=(interval,), daemon=True)
    voting_thread.start()

    print("=============================================")
    print("Bot is running. Press Ctrl+C to stop.")
    print("Check the logs directory for detailed logs.")
    print("Check the screenshots directory for visual debugging.")
    print("=============================================")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()

if __name__ == "__main__":
    run_bot()