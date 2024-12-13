# Set the maximum page to scrape
max_page = 12449  # Set this to the last known valid page ID

# Initialize scraping logic
page = start_page
image_counter = 1  # Initialize image counter
base_url = "https://www.designers-osaka-chintai.info/detail/id/"

while page <= max_page:  # Add the condition to end the loop
    url = f"{base_url}{page}"
    print(f"Accessing URL: {url}")
    driver.get(url)

    # Wait for page to load
    time.sleep(3)

    # Check if redirected to homepage and skip the page
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    if driver.current_url == "https://www.designers-osaka-chintai.info/" and not soup.find('div', class_='main clearFix'):
        print(f"URL redirected to homepage {driver.current_url}. Skipping.")
        save_last_page(LAST_PAGE_FILE, page)
        page += 1
        continue

    # Create a unique folder for each page ID
    page_folder = os.path.join(script_directory, str(page))
    if not os.path.exists(page_folder):
        os.makedirs(page_folder)
        print(f"Folder created: {page_folder}")

    # CSV File setup within the page folder
    csv_filename = os.path.join(page_folder, "property_details.csv")
    with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow([
            "Page ID", "Title", "Rental Details", "Google Maps URL", "Property Description"
        ])

    # Retry mechanism for loading the page
    retry_count = 0
    max_retries = 3
    while retry_count < max_retries:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        property_detail = soup.find('div', class_='main clearFix')
        if property_detail:
            break
        print(f"Retrying page {page}... Attempt {retry_count + 1}")
        time.sleep(2)
        retry_count += 1

    if not property_detail:
        print(f"Page {page} - No details found after retries. Skipping.")
        save_last_page(LAST_PAGE_FILE, page)
        page += 1
        continue

    # Extract property details
    title = property_detail.find('h1').text.strip() if property_detail.find('h1') else 'No title'
    print(f"Page ID {page} - Title: {title}")

    # Extract all images
    images = soup.find_all('img')
    image_urls = [img['src'] for img in images if 'src' in img.attrs]
    if image_urls:
        for img_url in image_urls:
            if img_url.startswith('http'):
                img_name = os.path.basename(img_url)
                current_date = datetime.now().strftime("%Y%m%d")
                new_img_name = f"Maido{current_date}_{image_counter}.jpg"
                img_path = os.path.join(page_folder, new_img_name)
                img_data = requests.get(img_url).content
                with open(img_path, 'wb') as handler:
                    handler.write(img_data)
                print(f"Downloaded image: {img_url} as {new_img_name}")
                image_counter += 1

    # Save data to CSV
    rental_details = "Example rental details"  # Replace with your actual extraction logic
    with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow([page, title, rental_details, "Google Maps URL", "Property Description"])

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