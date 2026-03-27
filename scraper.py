import requests
from bs4 import BeautifulSoup
import csv
import time
import os
import random
from datetime import datetime

# --- CONFIGURATION ---
TERM = "202608" # Fall 2026
WATCHLIST = ["CMSC216", "MATH141", "CMSC132"] # Add the classes you are sniping here!

BASE_URL = f"https://app.testudo.umd.edu/soc/{TERM}"
SECTIONS_URL = f"https://app.testudo.umd.edu/soc/{TERM}/sections?courseIds="

# --- DYNAMIC FILE PATHING ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')

def get_csv_path():
    """Ensures the data directory exists and returns the path for today's CSV."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    # Creates a filename like '2026-03-27.csv'
    current_date = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(DATA_DIR, f"{current_date}.csv")

# Masking our script to look like a normal Chrome browser executing an AJAX call
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest" 
}

# --- DISCORD ALERT FUNCTION ---
def send_discord_alert(message, channel_type="alert"):
    """Routes a message to the correct Discord webhook channel."""
    
    if channel_type == "log":
        webhook_url = os.environ.get('DISCORD_WEBHOOK_LOGS')
    elif channel_type == "error":
        webhook_url = os.environ.get('DISCORD_WEBHOOK_ERRORS')
    else: # Defaults to the "alert" channel for seat openings
        webhook_url = os.environ.get('DISCORD_WEBHOOK_ALERTS')
        
    if not webhook_url:
        return # Silently skip if the webhook is missing or not set up

    try:
        requests.post(webhook_url, json={"content": message})
    except Exception as e:
        print(f"Failed to send Discord alert to {channel_type}: {e}")

# --- SCRAPER FUNCTIONS ---
def get_department_prefixes():
    """Scrapes the main SOC page to get a list of all department prefixes."""
    response = requests.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    prefixes = []
    for prefix_elem in soup.find_all('span', class_='prefix-abbrev'):
        prefixes.append(prefix_elem.text.strip())
        
    return prefixes

def save_to_csv(data):
    if not data:
        return 
        
    target_path = get_csv_path() # <--- Use the function here
    file_exists = os.path.isfile(target_path)
    
    with open(target_path, mode='a', newline='', encoding='utf-8') as file:
        # ... rest of your code ...
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Course', 'Section', 'Instructor', 'Total_Seats', 'Open_Seats', 'Waitlist'])
        writer.writerows(data)

def scrape_departments(prefixes, batch_timestamp):
    """Loops through departments, grabs course IDs, and fetches sections via AJAX."""
    total_sections_scraped = 0
    
    for prefix in prefixes:
        print(f"Scraping {prefix}...", end=" ")
        dept_url = f"{BASE_URL}/{prefix}"
        
        try:
            # Step 1: Get all Course IDs (e.g., CMSC131, CMSC132)
            response = requests.get(dept_url, headers=HEADERS)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            course_divs = soup.find_all('div', class_='course-id')
            course_ids = [div.text.strip() for div in course_divs]
            
            if not course_ids:
                print("Saved 0 sections.")
                continue
                
            dept_data = []
            
            # Step 2: Hit the hidden AJAX endpoint for each course
            for course_id in course_ids:
                ajax_url = f"{SECTIONS_URL}{course_id}"
                ajax_response = requests.get(ajax_url, headers=HEADERS)
                ajax_soup = BeautifulSoup(ajax_response.text, 'html.parser')
                
                sections = ajax_soup.find_all('div', class_='section')
                
                for section in sections:
                    section_id = section.find('span', class_='section-id').text.strip()
                    total_seats = section.find('span', class_='total-seats-count').text.strip()
                    open_seats = section.find('span', class_='open-seats-count').text.strip()
                    waitlist = section.find('span', class_='waitlist-count').text.strip()
                    
                    instructor_elem = section.find('span', class_='section-instructor')
                    instructor = instructor_elem.text.strip() if instructor_elem else "TBA"
                    
                    dept_data.append([batch_timestamp, course_id, section_id, instructor, total_seats, open_seats, waitlist])
                    
                    # --- THE SPECIFIC SEAT ALERT LOGIC ---
                    open_seats_int = int(open_seats) if open_seats.isdigit() else 0
                    if course_id in WATCHLIST and open_seats_int > 0:
                        send_discord_alert(f"🚨 **SEAT OPEN!** {course_id} (Sec {section_id}) has {open_seats_int} seats! Taught by: {instructor}")
                
                # Micro-delay between courses
                time.sleep(0.1) 
                
            # Save this department's data immediately
            save_to_csv(dept_data)
            total_sections_scraped += len(dept_data)
            print(f"Saved {len(dept_data)} sections.")
            
        except Exception as e:
            print(f"Failed! Error: {e}")
            
        # Delay before the next department to avoid IP bans
        time.sleep(1)
        
    return total_sections_scraped

# --- MAIN EXECUTION BLOCK ---
if __name__ == "__main__":
    start_time_obj = datetime.now()
    batch_timestamp = start_time_obj.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"Starting university-wide scrape at {batch_timestamp}")
    print(f"Data will be saved to the 'data/' directory.\n")
    
    # 1. SEND START ALERT -> Logs Channel
    send_discord_alert(f"▶️ **Testudo Scraper Started** at {batch_timestamp}", "log")

    try:
        prefixes = get_department_prefixes()
        print(f"Found {len(prefixes)} departments to scrape.\n")
        
        # Run the massive loop, passing the fixed timestamp down
        total_saved = scrape_departments(prefixes, batch_timestamp)
        
        # Calculate execution time
        end_time_obj = datetime.now()
        duration_mins = round((end_time_obj - start_time_obj).total_seconds() / 60, 2)
        
        print(f"\nDone! Successfully scraped {total_saved} total sections in {duration_mins} minutes.")
        
        # 2. SEND SUCCESS ALERT -> Logs Channel
        send_discord_alert(f"✅ **Testudo Scraper Finished!** Scraped {total_saved} sections in {duration_mins} minutes.", "log")
        
    except Exception as e:
        error_msg = f"❌ **Scraper Crashed!** Error: {e}"
        print(f"Critical error: {e}")
        
        # 3. SEND CRASH ALERT -> To BOTH Logs and Errors Channels
        send_discord_alert(error_msg, "log")
        send_discord_alert(error_msg, "error")
