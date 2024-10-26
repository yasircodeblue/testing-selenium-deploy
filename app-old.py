from flask import Flask, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import cloudinary
import cloudinary.uploader
import time
import os
from io import BytesIO

app = Flask(__name__)
app.static_folder = './public'

# Configure Cloudinary
cloudinary.config(
    cloud_name='dsfr7nm3a',
    api_key='914261393664548',
    api_secret='7uckXI5naaQOjW8xnQ_G34YrRB0'
)

AIRTABLE_API_KEY = 'patnIFlyamWZtgthM.886ac387e5e38b76b059aa8c468abb0c7e7b3959917c7c993c619ce92c918057'

def fetch_record(table_id, record_id, airtable_base_id):
    """Fetch a record from Airtable"""
    try:
        response = requests.get(
            f'https://api.airtable.com/v0/{airtable_base_id}/{table_id}/{record_id}',
            headers={'Authorization': f'Bearer {AIRTABLE_API_KEY}'}
        )
        response.raise_for_status()
        return response.json()
    except Exception as error:
        print(f"Error fetching record: {error}")
        raise

def fetch_specific_payload(base_id, webhook_id, timestamp):
    """Fetch a specific payload using the timestamp"""
    try:
        response = requests.get(
            f'https://api.airtable.com/v0/bases/{base_id}/webhooks/{webhook_id}/payloads',
            headers={'Authorization': f'Bearer {AIRTABLE_API_KEY}'}
        )
        response.raise_for_status()
        
        webhook_time = time.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        print(f"Looking for webhook timestamp: {timestamp}")
        
        # Sort payloads by timestamp in descending order
        sorted_payloads = sorted(
            response.json()['payloads'],
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        # Find matching payload within 1 second
        for payload in sorted_payloads:
            payload_time = time.strptime(payload['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
            time_diff = time.mktime(webhook_time) - time.mktime(payload_time)
            if 0 <= time_diff <= 1:
                print(f"Found matching payload with timestamp: {payload['timestamp']}")
                return payload
                
        print("No payload found matching webhook timestamp")
        return None
    except Exception as error:
        print(f"Error fetching payload: {error}")
        raise

def upload_to_cloudinary(image_bytes):
    """Upload an image to Cloudinary"""
    try:
        result = cloudinary.uploader.upload(
            image_bytes,
            resource_type="image",
            upload_preset="pinterest"
        )
        print(f"Screenshot uploaded to Cloudinary: {result['secure_url']}")
        return result['secure_url']
    except Exception as error:
        print(f"Error uploading to Cloudinary: {error}")
        raise

def setup_chrome_driver():
    """Setup Chrome WebDriver with proper options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1900,1024')
    
    # Install or update ChromeDriver
    service = Service(ChromeDriverManager().install())
    
    return webdriver.Chrome(service=service, options=chrome_options)

def run_selenium(text):
    """Run Selenium automation"""
    driver = None
    try:
        # Initialize WebDriver
        print("Initializing Chrome WebDriver...")
        driver = setup_chrome_driver()
        
        print("Navigating to website...")
        driver.get("https://mockup.epiccraftings.com/")
        
        print("Waiting for textarea...")
        textarea = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".form-control.txt_area_1"))
        )
        textarea.clear()
        textarea.send_keys(text)
        
        print("Processing font divs...")
        # Add a small delay to ensure page is fully loaded
        time.sleep(2)
        font_divs = driver.find_elements(By.CSS_SELECTOR, "div.font-div[data-path]")[1:8]
        for div in font_divs:
            div.click()
            time.sleep(0.5)  # Small delay between clicks
        
        print("Waiting for screenshot element...")
        screenshot_elem = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "takeScreenShoot"))
        )
        
        # Add a small delay before taking screenshot
        time.sleep(2)
        
        print("Taking screenshot...")
        screenshot = driver.get_screenshot_as_png()
        
        print("Uploading to Cloudinary...")
        image_url = upload_to_cloudinary(BytesIO(screenshot))
        
        return image_url
        
    except Exception as error:
        print(f"Selenium error: {error}")
        raise
    finally:
        if driver:
            try:
                driver.quit()
                print("Browser closed successfully")
            except Exception as e:
                print(f"Error closing browser: {e}")

@app.route('/airtable-webhook', methods=['POST'])
def process_webhook():
    """Handle Airtable webhook"""
    print("Webhook received:", request.json)
    
    try:
        body = request.json
        base_id = body['base']['id']
        webhook_id = body['webhook']['id']
        timestamp = body['timestamp']
        target_field_id = "fldEpaZERjNqdVqIA"
        
        payload = fetch_specific_payload(base_id, webhook_id, timestamp)
        if not payload:
            return '', 200
            
        changed_tables = payload.get('changedTablesById', {})
        table_changes = changed_tables.get('tblgMDhb1xvmg72ha', {})
        changed_records = table_changes.get('changedRecordsById', {})
        
        record_details = None
        for record_id, record_changes in changed_records.items():
            changed_field_ids = record_changes.get('current', {}).get('cellValuesByFieldId', {}).keys()
            
            if target_field_id not in changed_field_ids:
                continue
                
            record_details = fetch_record('tblgMDhb1xvmg72ha', record_id, base_id)
            mockup_text = record_details.get('fields', {}).get('Mokcup Text')
            if mockup_text:
                image_url = run_selenium(mockup_text)
                print(f"Generated image URL: {image_url}")
        
        return jsonify(record_details or {})
    except Exception as error:
        print(f"Failed to process webhook: {error}")
        return jsonify({"error": str(error)}), 500

@app.route('/')
def home():
    return "App is running"

@app.route('/new-req')
def new_req():
    try:
        image_url = run_selenium("Someone name")
        return jsonify({"msg": "API successfully called", "image_url": image_url})
    except Exception as error:
        return jsonify({"msg": "An error occurred", "error": str(error)}), 500

if __name__ == '__main__':
    app.run(port=5000)