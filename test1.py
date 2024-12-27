import os
import re
import time
import requests
import logging
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import json

# Configuration
CHROMIUM_DRIVER_PATH = os.getenv("CHROMIUM_DRIVER_PATH", "/usr/bin/chromedriver")
BASE_URL = "https://www.designers-osaka-chintai.info/detail/id/"
MAX_CONSECUTIVE_INVALID = 10
MAX_RETRIES = 3
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./scraped_data")
START_PAGE = 12453  # Default starting page
GITHUB_PAT = os.getenv("GITHUB_PAT")

# Logging Configuration
LOG_FORMAT = "%(asctime)s [%(levelname)s]: %(message)s"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT)

# Check GitHub PAT
if not GITHUB_PAT:
    logging.error("GITHUB_PAT is not set. Check your environment and GitHub Actions secrets.")
    exit(1)
else:
    logging.info(f"GITHUB_PAT is set. Length: {len(GITHUB_PAT)} characters.")

# Git Helper Functions
def configure_git():
    try:
        subprocess.run(["git", "config", "user.name", "MaidoEstate"], check=True)
        subprocess.run(["git", "config", "user.email", "Alan@real-estate-osaka.com"], check=True)
        logging.info("Git user identity configured.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to configure Git user identity: {e}")

def pull_latest_changes():
    try:
        subprocess.run(["git", "stash"], check=True)  # Stash uncommitted changes
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        logging.info("Pulled latest changes from GitHub.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to pull latest changes from GitHub: {e}")
        exit(1)

def commit_and_push(file_path):
    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", "Update last_page.txt via script"], check=True)
        subprocess.run(
            ["git", "push", f"https://{GITHUB_PAT}@github.com/MaidoEstate/Maido-script.git", "HEAD:main"],
            check=True,
        )
        logging.info(f"Committed and pushed {file_path} to GitHub.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to commit and push {file_path} to GitHub: {e}")
        exit(1)

# Scraper Functions
def download_image(img_url, folder, image_counter, page_id):
    img_name = os.path.basename(img_url)
    if re.match(r'^\d', img_name):  # Image name starts with a digit
        for attempt in range(MAX_RETRIES):
            try:
                img_data = requests.get(img_url, timeout=10).content
                new_img_name = f"Maido_{datetime.now().strftime('%Y%m%d')}_{image_counter}.jpg"
                img_path = os.path.join(folder, new_img_name)
                with open(img_path, "wb") as f:
                    f.write(img_data)
                logging.info(f"Downloaded image for page {page_id}: {img_url} -> {new_img_name}")
                return new_img_name
            except Exception as e:
                logging.error(f"Failed to download image from page {page_id}: {e}")
        return None
    else:
        logging.info(f"Image {img_name} skipped as it does not start with a digit.")
        return None

def scrape_page(page_id, output_dir):
    url = f"{BASE_URL}{page_id}"
    logging.info(f"Accessing URL: {url}")
    try:
        driver.get(url)
        time.sleep(2)
        if driver.current_url == "https://www.designers-osaka-chintai.info/":  # Redirected to homepage
            logging.warning(f"Page {page_id} redirected to homepage. Skipping.")
            return False

        soup = BeautifulSoup(driver.page_source, "html.parser")
        page_folder = os.path.join(output_dir, str(page_id))
        os.makedirs(page_folder, exist_ok=True)

        # Extract details and images
        property_data = {
            "page_id": page_id,
            "title": soup.find("h1").text.strip() if soup.find("h1") else "No title",
            "description": soup.find("div", class_="description").text.strip() if soup.find("div", "description") else "No description",
            "big_images": [],
            "small_images": [],
        }

        image_counter = 1
        for img_tag in soup.find_all("img"):
            img_url = img_tag.get("src")
            if img_url and img_url.startswith("http"):
                downloaded_image = download_image(img_url, page_folder, image_counter, page_id)
                if downloaded_image:
                    if "big" in img_url.lower():
                        property_data["big_images"].append(downloaded_image)
                    else:
                        property_data["small_images"].append(downloaded_image)
                    image_counter += 1

        # Save property details to JSON
        json_path = os.path.join(page_folder, f"property_{page_id}.json")
        with open(json_path, "w", encoding="utf-8") as jsonfile:
            json.dump(property_data, jsonfile, indent=4, ensure_ascii=False)

        logging.info(f"Page {page_id} scraped successfully.")
        return True

    except Exception as e:
        logging.error(f"Error scraping page {page_id}: {e}")
        return False

# Main Function
def main():
    pull_latest_changes()  # Ensure we start with the latest GitHub state
    configure_git()

    try:
        with open("last_page.txt", "r") as f:
            current_page = int(f.read().strip()) + 1
    except (FileNotFoundError, ValueError):
        current_page = START_PAGE

    consecutive_invalid = 0
    while consecutive_invalid < MAX_CONSECUTIVE_INVALID:
        logging.info(f"Scraping page {current_page}...")
        success = scrape_page(current_page, OUTPUT_DIR)
        if success:
            # Update last_page.txt
            with open("last_page.txt", "w") as f:
                f.write(str(current_page))
            commit_and_push("last_page.txt")
            consecutive_invalid = 0  # Reset invalid counter
        else:
            consecutive_invalid += 1
            logging.warning(f"Page {current_page} invalid. Consecutive invalid: {consecutive_invalid}")

        # Increment page regardless of success
        current_page += 1

if __name__ == "__main__":
    # Selenium setup
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    service = Service(CHROMIUM_DRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        main()
    finally:
        driver.quit()
