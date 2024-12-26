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
    try:
        # Pull the latest changes from the remote repository
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=True)
        
        # Add and commit the file
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", "Update last_page.txt via script"], check=True)
        
        # Push the changes to the remote repository
        subprocess.run(
            ["git", "push", f"https://{GITHUB_PAT}@github.com/MaidoEstate/Maido-script.git", "HEAD:main"],
            check=True,
        )
        logging.info(f"Committed and pushed {file_path} to Git.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to commit and push {file_path} to Git: {e}")

# Download and rename images
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
                if attempt == MAX_RETRIES - 1:
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
        os.makedirs(page_folder, exist_ok=True)

        # Extract property details
        property_detail = soup.find("div", class_="main clearFix")
        if not property_detail:
            logging.warning(f"No property details found on page {page_id}.")
            return False
        
        title = property_detail.find("h1").text.strip() if property_detail.find("h1") else "No title"
        description = soup.find("div", class_="description").text.strip() if soup.find("div", "description") else "No description"
        rental_details = "Example rental details"  # Placeholder, replace with actual logic
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
        csv_filename = os.path.join(page_folder, "property_details.csv")
        with open(csv_filename, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["Page ID", "Title", "Rental Details", "Description"])
            csv_writer.writerow([page_id, title, rental_details, description])

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