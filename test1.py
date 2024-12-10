from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import requests
import os
import time
import re
from datetime import datetime
import csv

# Set up Selenium WebDriver
chrome_options = Options()
chrome_options.add_argument("--headless")  # Optional: Run in headless mode
service = Service('/usr/local/bin/chromedriver')  # Using the same path as you had before

driver = webdriver.Chrome(service=service, options=chrome_options)

# Get starting page ID from user input
start_page = int(input("Enter the starting page ID: "))
base_url = "https://www.designers-osaka-chintai.info/detail/id/"

# Folder to save images
image_folder = "downloaded_images"
if not os.path.exists(image_folder):
    os.makedirs(image_folder)

# Get current date in the format YYYYMMDD
current_date = datetime.now().strftime("%Y%m%d")

# CSV File setup
csv_filename = "property_details.csv"
with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([
        "Page ID", "Title", "Rental Details", "Google Maps URL", "Property Description",
        "Building Type", "Location", "Structure", "Parking",
        "Room Type", "Elevator", "Completion Date", "Number of Units",
        "Building Equipment", "Transport Info", "Room Info",
        "Room Rent", "Area", "Deposit", "Key Money", "Utility Costs", "Management Fee", 
        "Balcony Orientation", "Room Equipment"
    ])

# Start scraping from the specified page ID
page = start_page
image_counter = 1  # Initialize image counter

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

    # Use BeautifulSoup to parse the page source
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Extract property details
    property_detail = soup.find('div', class_='main clearFix')
    if property_detail:
        # Extract property title
        title = property_detail.find('h1').text.strip() if property_detail.find('h1') else 'No title'
        print(f"Page ID {page} - Title: {title}")

        # Extract all images
        images = soup.find_all('img')
        image_urls = [img['src'] for img in images if 'src' in img.attrs]
        if image_urls:
            print("Images found:")
            for img_url in image_urls:
                if img_url.startswith('http'):
                    # Get the image name from the URL
                    img_name = os.path.basename(img_url)

                    # Only download images whose names start with a number
                    if re.match(r'^\d', img_name):
                        # Create new image name with format MaidoYYYYMMDD_<number>
                        new_img_name = f"Maido{current_date}_{image_counter}.jpg"
                        img_path = os.path.join(image_folder, new_img_name)

                        try:
                            # Download the image
                            img_data = requests.get(img_url).content
                            with open(img_path, 'wb') as handler:
                                handler.write(img_data)
                            
                            print(f"Downloaded image: {img_url} as {new_img_name}")
                            image_counter += 1  # Increment image counter
                        except Exception as e:
                            print(f"Failed to download {img_name}: {e}")

        # Extract rental details
        rental_details = ""
        rental_table = property_detail.find('table')
        if rental_table:
            rental_details = []
            for row in rental_table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key, value = cells[0].text.strip(), cells[1].text.strip()
                    rental_details.append(f"{key}: {value}")
            rental_details = "\n".join(rental_details)

        # Extract address from Google Maps
        address_section = soup.find('iframe', {'src': lambda x: x and 'maps.google.co.jp' in x})
        address_url = address_section['src'] if address_section else ""

        # Extract property description text (specific content)
        description_section = property_detail.find('div', class_='txtArea')
        property_description = description_section.get_text(separator="\n", strip=True) if description_section else ""

        # Extract additional building info
        tables = property_detail.find_all('table')
        building_info, room_info = "", ""
        if len(tables) > 1:
            building_info_table = tables[0]
            building_info = []
            for row in building_info_table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key, value = cells[0].text.strip(), cells[1].text.strip()
                    building_info.append(f"{key}: {value}")
            building_info = "\n".join(building_info)
        
        if len(tables) > 2:
            room_info_table = tables[1]
            room_info = []
            for row in room_info_table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) == 2:
                    key, value = cells[0].text.strip(), cells[1].text.strip()
                    room_info.append(f"{key}: {value}")
            room_info = "\n".join(room_info)

        # Write to CSV
        with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([
                page, title, rental_details, address_url, property_description,
                building_info, room_info
            ])

    else:
        print(f"Page ID {page} - No details found.")

    # Increment the page ID
    page += 1

    # Add a delay of 2 seconds between requests to avoid overwhelming the server
    time.sleep(2)

# Quit the WebDriver
driver.quit()