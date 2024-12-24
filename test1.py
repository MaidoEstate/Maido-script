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
    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", "Update last_page.txt via script"], check=True)
        subprocess.run(
            ["git", "push", f"https://{GITHUB_PAT}@github.com/MaidoEstate/Maido-script.git", "main"],
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

# Helper: Create directory if it doesn't exist
def create_directory(path):
    if not os.path.exists(path):
        os.makedirs(path)

# Helper: Download and rename image with retries
def download_image(img_url, folder, image_counter, page_id):
    img_name = os.path.basename(img_url)
    if re.match(r'^\d', img_name):  # Check if the image name starts with a digit
        for attempt in range(MAX_RETRIES):
            try:
                img_data = requests.get(img_url, timeout=10).content
                current_date = datetime.now().strftime("%Y%m%d")
                new_img_name = f"Maido{current_date}_{image_counter}.jpg"
                img_path = os.path.join(folder, new_img_name)
                with open(img_path, "wb") as f:
                    f.write(img_data)
                logging.info(f"Downloaded and renamed image for page {page_id}: {img_url} -> {new_img_name}")
                return new_img_name
            except Exception as e:
                if attempt == MAX_RETRIES - 1:  # Log error if all retries fail
                    logging.error(f"Failed to download image from page {page_id}: {img_url}: {e}")
        return None
    else:
        logging.info(f"Image {img_name} skipped as it does not start with a digit.")
        return None

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
        create_directory(page_folder)

        # CSV File setup within the page folder
        csv_filename = os.path.join(page_folder, "property_details.csv")
        with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Page ID", "Title", "Rental Details", "Google Maps URL", "Property Description"])

        # Extract property details
        property_detail = soup.find("div", class_="main clearFix")
        if property_detail:
            title = property_detail.find("h1").text.strip() if property_detail.find("h1") else "No title"
            description = soup.find("div", class_="description").text.strip() if soup.find("div", "description") else "No description"
            logging.info(f"Page {page_id} - Title: {title}")

            # Download and rename all images
            image_counter = 1
            image_tags = soup.find_all("img")
            for img_tag in image_tags:
                img_url = img_tag.get("src")
                if img_url and img_url.startswith("http"):
                    download_image(img_url, page_folder, image_counter, page_id)
                    image_counter += 1

            # Save data to CSV
            rental_details = "Example rental details"  # Replace with actual logic
            with open(csv_filename, "a", newline="", encoding="utf-8") as csvfile:
                csv_writer = csv.writer(csvfile)
                csv_writer.writerow([page_id, title, rental_details, "Google Maps URL", description])

            logging.info(f"Page {page_id} scraped successfully.")
            return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return None

# Main scraper loop
def main():
    global current_page  # Reference the global current_page
    consecutive_invalid = 0
    create_directory(OUTPUT_DIR)

    # Configure Git before starting
    configure_git()

    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        logging.info(f"Scraping page {current_page}...")
        result = scrape_page(current_page, OUTPUT_DIR)
        if result:
            consecutive_invalid = 0  # Reset on success
            # Write the current page to the last_page.txt file
            with open("last_page.txt", "w") as file:
                file.write(str(current_page))
            # Commit the updated file to Git
            commit_to_git("last_page.txt")
        else:
            consecutive_invalid += 1  # Increment on failure
            logging.warning(f"Consecutive invalid pages: {consecutive_invalid}")
        current_page += 1

    logging.info("Scraping complete. Exiting.")
    graceful_exit()

# Start the scraper
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        graceful_exit()
