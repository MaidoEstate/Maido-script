import os
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime
import csv
import re

# Environment variables for ChromeDriver and the last processed page file
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH", "/usr/bin/chromedriver")
LAST_PAGE_FILE = os.getenv("LAST_PAGE_FILE", "last_page.txt")

# Function to read the last processed page
def read_last_page(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            return int(file.read().strip())
    return None

# Function to save the last processed page
def save_last_page(file_path, last_page):
    with open(file_path, 'w') as file:
        file.write(str(last_page))

# Set up ChromeDriver
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=chrome_options)

# Get the path where the script is located
script_directory = os.path.dirname(os.path.abspath(__file__))

# Initialize the starting page
last_processed_page = read_last_page(LAST_PAGE_FILE)
if last_processed_page is not None:
    print(f"Resuming from page {last_processed_page + 1}")
    start_page = last_processed_page + 1  # Start from the next page
else:
    try:
        start_page = int(input("Enter the starting page ID: "))  # Prompt the user
    except ValueError:
        print("Invalid input. Please enter a numeric starting page ID.")
        driver.quit()
        exit(1)

# Set the current page to start_page
page = start_page
image_counter = 1  # Initialize image counter
base_url = "https://www.designers-osaka-chintai.info/detail/id/"

while True:
    url = f"{base_url}{page}"
    print(f"Accessing URL: {url}")
    driver.get(url)

    # Wait for page to load
    time.sleep(3)

    # Check if redirected to homepage
    if driver.current_url == "https://www.designers-osaka-chintai.info/":
        print(f"URL redirected to homepage {driver.current_url}. Stopping.")
        break

    # Create a unique folder for each page ID within the script's directory
    page_folder = os.path.join(script_directory, str(page))
    if not os.path.exists(page_folder):
        os.makedirs(page_folder)
        print(f"Folder created: {page_folder}")

    # CSV File setup within the page folder
    csv_filename = os.path.join(page_folder, "property_details.csv")
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["Page ID", "Title", "Rental Details", "Google Maps URL", "Property Description"])

    # Use BeautifulSoup to parse the page source
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract property details
    property_detail = soup.find('div', class_='main clearFix')
    if property_detail:
        title = property_detail.find('h1').text.strip() if property_detail.find('h1') else 'No title'
        print(f"Page ID {page} - Title: {title}")

        # Extract all images
        images = soup.find_all('img')
        image_urls = [img['src'] for img in images if 'src' in img.attrs]
        if image_urls:
            for img_url in image_urls:
                if img_url.startswith('http'):
                    img_name = os.path.basename(img_url)
                    if re.match(r'^\d', img_name):
                        current_date = datetime.now().strftime("%Y%m%d")
                        new_img_name = f"Maido{current_date}_{image_counter}.jpg"
                        img_path = os.path.join(page_folder, new_img_name)
                        img_data = requests.get(img_url).content
                        with open(img_path, 'wb') as handler:
                            handler.write(img_data)
                        print(f"Downloaded image: {img_url} as {new_img_name}")
                        image_counter += 1

        # Save data to CSV
        rental_details = "Example rental details"  # Replace with actual extraction logic
        with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([page, title, rental_details, "Google Maps URL", "Property Description"])

    else:
        print(f"Page ID {page} - No details found.")

    # Save the last processed page
    save_last_page(LAST_PAGE_FILE, page)
    print(f"Saved last page: {page}")

    # Increment page for the next iteration
    page += 1

    # Add a delay of 2 seconds between requests to avoid overwhelming the server
    time.sleep(2)

# Quit the WebDriver
driver.quit()

print(f"Scraping completed. Last processed page: {page - 1}")