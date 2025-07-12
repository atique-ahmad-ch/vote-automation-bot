from flask import Flask, jsonify, request
from flask_cors import CORS
import logging
import threading
import time
from faker import Faker
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc
import schedule
import random
import os
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# Global bot instance
bot_instance = None

# Configure logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(log_dir, f"voting-bot-api-{time.strftime('%Y%m%d-%H%M%S')}.log")),
        logging.StreamHandler()
    ]
)

fake = Faker('de_DE')

# List of vote targets
SITES = [
    {"name": "HR4", "url": "https://www.hr4.de/musik/die-ard-schlagerhitparade/abstimmung-zur-hr4-hitparade-v3,hr4-hitparade-abstimmung-100.html"},
    {"name": "MDR", "url": "https://www.mdr.de/sachsenradio/programm/deutschehitparade106.html"},
    {"name": "SWR", "url": "https://www.swr.de/schlager/voting-abstimmung-ard-schlagerhitparade-136.html"},
]

class VotingBotAPI:
    def __init__(self):
        self.successful_votes = 0
        self.failed_votes = 0
        self.total_attempts = 0
        self.running = False
        self.session_id = str(uuid.uuid4())
        self.start_time = None
        self.voting_thread = None
        self.current_interval = 30
        self.last_vote_time = None
        self.vote_history = []
        logging.debug("VotingBotAPI initialized")

    def setup_browser(self):
        logging.debug("Setting up undetected browser for server deployment...")
        
        options = uc.ChromeOptions()
        
        # Server-optimized settings
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--disable-javascript")
        options.add_argument("--disable-css")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--single-process")
        options.add_argument("--no-zygote")
        options.add_argument("--memory-pressure-off")
        options.add_argument("--max_old_space_size=4096")

        # Random user agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.55 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36"
        ]
        selected_agent = random.choice(user_agents)
        options.add_argument(f"user-agent={selected_agent}")

        try:
            driver = uc.Chrome(
                options=options,
                version_main=137,
                headless=True,
                use_subprocess=True
            )
            logging.debug("Browser setup successful")
            return driver
        except Exception as e:
            logging.error(f"Error setting up browser: {e}")
            return None

    def debug_page(self, driver, step_name):
        logging.debug(f"--- DEBUG {step_name} ---")
        logging.debug(f"Current URL: {driver.current_url}")
        logging.debug(f"Page title: {driver.title}")

    def handle_cookie_consent(self, driver):
        try:
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
                    cookie_button.click()
                    time.sleep(2)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def vote_on_hr4(self, driver):
        try:
            # Accept cookies if present
            try:
                cookie_button = driver.find_element(By.CSS_SELECTOR, "[data-testid='gdpr-accept-all']")
                cookie_button.click()
                time.sleep(1)
            except:
                pass

            # Locate voting checkboxes
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='multivoting']")
            if len(checkboxes) < 2:
                raise Exception(f"Expected at least 2 voting checkboxes, found {len(checkboxes)}")

            selected = random.sample(checkboxes, 2)
            for box in selected:
                driver.execute_script("arguments[0].scrollIntoView(true);", box)
                driver.execute_script("arguments[0].click();", box)

            # Submit vote
            submit_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Abstimmen']")
            driver.execute_script("arguments[0].removeAttribute('disabled');", submit_button)
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(3)

            # Check for success
            success_msg = driver.find_elements(By.CSS_SELECTOR, "p.text-success")
            if success_msg:
                return True

            page_text = driver.page_source.lower()
            if "danke" in page_text or "ergebnis" in page_text:
                return True

            return False

        except Exception as e:
            logging.error(f"HR4 voting failed: {e}")
            return False

    def vote_on_mdr(self, driver):
        try:
            self.debug_page(driver, "mdr-initial-load")

            # Find voting buttons
            voting_buttons = driver.find_elements(By.CSS_SELECTOR, ".wertungspad button.okaytoggle")
            if not voting_buttons:
                raise Exception("No voting buttons found")

            visible_buttons = [btn for btn in voting_buttons if btn.is_displayed()]
            if not visible_buttons:
                raise Exception("Voting buttons not visible")

            random_button = random.choice(visible_buttons)
            driver.execute_script("arguments[0].scrollIntoView(true);", random_button)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", random_button)

            # Fill form with fake data
            try:
                name = fake.name()
                address = fake.address().replace('\n', ', ')
                email = fake.email()

                driver.find_element(By.NAME, "ff1").send_keys(name)
                driver.find_element(By.NAME, "ff2").send_keys(address)
                driver.find_element(By.NAME, "ff3").send_keys(email)
            except Exception as e:
                logging.error("Error filling MDR form")
                raise Exception("Form fields not found")

            # Submit
            submit_button = driver.find_element(By.CSS_SELECTOR, "button[name='Absenden']")
            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(3)

            # Check if buttons are gone (success indicator)
            remaining_buttons = driver.find_elements(By.CSS_SELECTOR, ".wertungspad button.okaytoggle")
            return not remaining_buttons

        except Exception as e:
            logging.error(f"MDR voting failed: {e}")
            return False

    def vote_on_swr(self, driver):
        try:
            # Find voting checkboxes
            checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='votingitem']")
            if len(checkboxes) < 3:
                raise Exception(f"Expected at least 3 voting checkboxes, found {len(checkboxes)}")

            selected = random.sample(checkboxes, 3)
            for box in selected:
                driver.execute_script("arguments[0].scrollIntoView(true);", box)
                driver.execute_script("arguments[0].click();", box)

            # Fill form with fake data
            try:
                name1 = fake.first_name()
                name2 = fake.last_name()
                email = fake.email()

                driver.find_element(By.NAME, "formField_vorname").send_keys(name1)
                driver.find_element(By.NAME, "formField_nachname").send_keys(name2)
                driver.find_element(By.NAME, "formField_email").send_keys(email)
            except Exception as e:
                logging.error("Error filling SWR form")
                raise Exception("Form fields not found")

            # Accept terms
            checkbox = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='formField_teilnahmebedingungen']")[0]
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            driver.execute_script("arguments[0].click();", checkbox)

            # Submit
            try:
                submit_button = driver.find_element(By.ID, "formSubmitButton")
            except:
                submit_button = driver.find_element(By.CSS_SELECTOR, "form button[type='submit'], form input[type='submit']")

            driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
            driver.execute_script("arguments[0].click();", submit_button)

            time.sleep(3)

            # Check for success
            page_text = driver.page_source.lower()
            return "vielen dank für ihre stimme" in page_text or "danke" in page_text

        except Exception as e:
            logging.error(f"SWR voting failed: {e}")
            return False

    def vote_on_site(self, site):
        logging.info(f"Starting vote on {site['name']}")
        driver = self.setup_browser()
        if not driver:
            return False

        try:
            driver.get(site["url"])
            time.sleep(5)

            if site["name"] == "HR4":
                success = self.vote_on_hr4(driver)
            elif site["name"] == "MDR":
                success = self.vote_on_mdr(driver)
            elif site["name"] == "SWR":
                success = self.vote_on_swr(driver)
            else:
                success = False

            # Log vote attempt
            self.vote_history.append({
                "site": site["name"],
                "timestamp": datetime.now().isoformat(),
                "success": success
            })

            if success:
                self.successful_votes += 1
                logging.info(f"Successfully voted on {site['name']}")
            else:
                self.failed_votes += 1
                logging.warning(f"Failed to vote on {site['name']}")

            return success

        except Exception as e:
            logging.error(f"Failed to vote on {site['name']}: {e}")
            self.failed_votes += 1
            return False
        finally:
            if driver:
                driver.quit()

    def vote_all(self):
        self.total_attempts += 1
        self.last_vote_time = datetime.now()
        logging.info(f"Starting voting cycle #{self.total_attempts}")

        results = {}
        for site in SITES:
            results[site["name"]] = self.vote_on_site(site)

        logging.info(f"Voting cycle #{self.total_attempts} completed")
        return results

    def start_scheduled_voting(self, interval_minutes):
        self.current_interval = interval_minutes
        self.start_time = datetime.now()
        
        # Clear previous schedule
        schedule.clear()
        
        # Schedule recurring votes
        schedule.every(interval_minutes).minutes.do(self.vote_all)

        while self.running:
            schedule.run_pending()
            time.sleep(1)

    def start_bot(self, interval_minutes=30):
        if self.running:
            return False, "Bot is already running"

        self.running = True
        self.voting_thread = threading.Thread(
            target=self.start_scheduled_voting, 
            args=(interval_minutes,), 
            daemon=True
        )
        self.voting_thread.start()
        return True, "Bot started successfully"

    def stop_bot(self):
        if not self.running:
            return False, "Bot is not running"

        self.running = False
        schedule.clear()
        return True, "Bot stopped successfully"

    def get_status(self):
        return {
            "session_id": self.session_id,
            "running": self.running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_vote_time": self.last_vote_time.isoformat() if self.last_vote_time else None,
            "interval_minutes": self.current_interval,
            "total_attempts": self.total_attempts,
            "successful_votes": self.successful_votes,
            "failed_votes": self.failed_votes,
            "success_rate": f"{(self.successful_votes / max(1, self.successful_votes + self.failed_votes)) * 100:.1f}%",
            "vote_history": self.vote_history[-10:]  # Last 10 votes
        }

# API Routes
@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current bot status"""
    global bot_instance
    if not bot_instance:
        return jsonify({"error": "Bot not initialized"}), 400
    
    return jsonify(bot_instance.get_status())

@app.route('/api/start', methods=['POST'])
def start_bot():
    """Start the voting bot"""
    global bot_instance
    
    data = request.get_json() or {}
    interval = data.get('interval_minutes', 30)
    
    if not isinstance(interval, int) or interval < 1:
        return jsonify({"error": "Invalid interval. Must be a positive integer."}), 400
    
    if not bot_instance:
        bot_instance = VotingBotAPI()
    
    success, message = bot_instance.start_bot(interval)
    
    if success:
        return jsonify({
            "message": message,
            "session_id": bot_instance.session_id,
            "interval_minutes": interval
        })
    else:
        return jsonify({"error": message}), 400

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    """Stop the voting bot"""
    global bot_instance
    
    if not bot_instance:
        return jsonify({"error": "Bot not initialized"}), 400
    
    success, message = bot_instance.stop_bot()
    
    if success:
        return jsonify({
            "message": message,
            "final_stats": bot_instance.get_status()
        })
    else:
        return jsonify({"error": message}), 400

@app.route('/api/vote-once', methods=['POST'])
def vote_once():
    """Execute a single voting cycle"""
    global bot_instance
    
    if not bot_instance:
        bot_instance = VotingBotAPI()
    
    try:
        results = bot_instance.vote_all()
        return jsonify({
            "message": "Single vote cycle completed",
            "results": results,
            "stats": bot_instance.get_status()
        })
    except Exception as e:
        return jsonify({"error": f"Vote failed: {str(e)}"}), 500

@app.route('/api/sites', methods=['GET'])
def get_sites():
    """Get list of voting sites"""
    return jsonify({"sites": SITES})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get recent log entries"""
    try:
        log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        if not log_files:
            return jsonify({"logs": []})
        
        latest_log = max(log_files, key=lambda f: os.path.getctime(os.path.join(log_dir, f)))
        log_path = os.path.join(log_dir, latest_log)
        
        with open(log_path, 'r') as f:
            lines = f.readlines()
            # Return last 50 lines
            recent_lines = lines[-50:] if len(lines) > 50 else lines
        
        return jsonify({
            "log_file": latest_log,
            "lines": recent_lines
        })
    except Exception as e:
        return jsonify({"error": f"Failed to read logs: {str(e)}"}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    logging.info("Starting Voting Bot API Server")
    app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)