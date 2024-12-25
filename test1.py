import os
import re
import time
import requests
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import subprocess

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
START_PAGE = int(os.getenv("START_PAGE", "12453"))
MAX_CONSECUTIVE_INVALID = 10
MAX_RETRIES = 3
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
GITHUB_PAT = os.getenv("GITHUB_PAT")  # GitHub PAT from environment variable

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Debugging PAT
if not GITHUB_PAT:
    logging.error("GITHUB_PAT is not set. Check your environment and GitHub Actions secrets.")
    exit(1)
else:
    logging.info(f"GITHUB_PAT is set. Length: {len(GITHUB_PAT)} characters.")

# Git Configuration
def configure_git():
    try:
        subprocess.run(["git", "config", "user.name", "MaidoEstate"], check=True)
        subprocess.run(["git", "config", "user.email", "Alan@real-estate-osaka.com"], check=True)
        logging.info("Git user identity configured.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to configure Git user identity: {e}")

# Function to commit the file to Git
def commit_to_git(file_path):
    if not GITHUB_PAT:
        logging.error("GITHUB_PAT is not set. Cannot push to GitHub.")
        return
    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", "Update last_page.txt via script"], check=True)
        subprocess.run(
            ["git", "push", f"https://{GITHUB_PAT}@github.com/MaidoEstate/Maido-script.git", "HEAD:main"],
            check=True,
        )
        logging.info(f"Committed and pushed {file_path} to Git.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to commit and push {file_path} to Git: {e}")

# Check if last_page.txt exists and get the starting page ID
last_processed_page = None
try:
    if os.path.exists("last_page.txt"):
        with open("last_page.txt", "r") as file:
            last_processed_page = int(file.read().strip())
except (FileNotFoundError, ValueError):
    logging.warning("No valid last_page.txt found. Starting from START_PAGE.")
    last_processed_page = None

# Start from the higher of START_PAGE or the saved last processed page
if last_processed_page is not None:
    current_page = max(START_PAGE, last_processed_page + 1)
else:
    current_page = START_PAGE

logging.info(f"Starting from page {current_page}")

# Validate environment configuration
if not os.path.exists(CHROMIUM_DRIVER_PATH):
    logging.error(f"Chromium driver not found at {CHROMIUM_DRIVER_PATH}. Check your environment variables.")
    exit(1)

# Selenium setup
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium-browser"
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMIUM_DRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Graceful exit
def graceful_exit():
    logging.info("Shutting down scraper.")
    driver.quit()

# Scraper: Process a single page
def scrape_page(page_id, output_dir):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Accessing URL: {url}")
    try:
        driver.get(url)
        time.sleep(2)

        # Check if redirected to homepage
        if driver.current_url == "https://www.designers-osaka-chintai.info/":
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return None

        # Parse page content
        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_folder = os.path.join(output_dir, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Write a placeholder CSV (extend with real logic later)
        csv_path = os.path.join(page_folder, "data.csv")
        with open(csv_path, "w") as f:
            f.write("placeholder data")

        logging.info(f"Page {page_id} scraped successfully.")
        return True
    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

# Main scraper loop
def main():
    global current_page
    consecutive_invalid = 0

    # Configure Git
    configure_git()

    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        logging.info(f"Scraping page {current_page}...")
        if scrape_page(current_page, OUTPUT_DIR):
            consecutive_invalid = 0
            with open("last_page.txt", "w") as f:
                f.write(str(current_page))
            commit_to_git("last_page.txt")
        else:
            consecutive_invalid += 1
        current_page += 1

    logging.info("Scraper complete.")
    graceful_exit()

if __name__ == "__main__":
    main()
