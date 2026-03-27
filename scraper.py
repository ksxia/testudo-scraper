import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from datetime import datetime

TERM = "202608" # Fall 2026
BASE_URL = f"https://app.testudo.umd.edu/soc/{TERM}"
# The hidden Testudo AJAX endpoint
SECTIONS_URL = f"https://app.testudo.umd.edu/soc/{TERM}/sections?courseIds="

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(SCRIPT_DIR, 'all_seat_counts.csv')

# Masking our script to look like a normal Chrome browser executing an AJAX call
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest" 
}

def get_department_prefixes():
    """Scrapes the main SOC page to get a list of all department prefixes."""
    response = requests.get(BASE_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    prefixes = []
    for prefix_elem in soup.find_all('span', class_='prefix-abbrev'):
        prefixes.append(prefix_elem.text.strip())
        
    return prefixes

def save_to_csv(data):
    """Saves a batch of data to the CSV file."""
    if not data:
        return 
        
    file_exists = os.path.isfile(CSV_FILE_PATH)
    
    with open(CSV_FILE_PATH, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Course', 'Section', 'Instructor', 'Total_Seats', 'Open_Seats', 'Waitlist'])
        writer.writerows(data)

def scrape_departments(prefixes):
    """Loops through departments, grabs course IDs, and fetches sections via AJAX."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_sections_scraped = 0
    
    for prefix in prefixes:
        print(f"Scraping {prefix}...", end=" ")
        dept_url = f"{BASE_URL}/{prefix}"
        
        try:
            # Step 1: Get all Course IDs for the department (e.g., AASP100)
            response = requests.get(dept_url, headers=HEADERS)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            course_divs = soup.find_all('div', class_='course-id')
            course_ids = [div.text.strip() for div in course_divs]
            
            if not course_ids:
                print("Saved 0 sections (No courses found).")
                continue
                
            dept_data = []
            
            # Step 2: Hit the hidden AJAX endpoint for each course
            for course_id in course_ids:
                ajax_url = f"{SECTIONS_URL}{course_id}"
                
                # Fetch the sections HTML directly
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
                    
                    dept_data.append([timestamp, course_id, section_id, instructor, total_seats, open_seats, waitlist])
                
                # A tiny micro-delay between individual courses to keep the WAF happy
                time.sleep(0.1) 
                
            # Save this department's data immediately
            save_to_csv(dept_data)
            total_sections_scraped += len(dept_data)
            print(f"Saved {len(dept_data)} sections.")
            
        except Exception as e:
            print(f"Failed! Error: {e}")
            
        # A slightly larger delay before jumping to the next department
        time.sleep(1)
        
    return total_sections_scraped

if __name__ == "__main__":
    try:
        print(f"Starting university-wide scrape at {datetime.now()}")
        print(f"Data will be saved to: {CSV_FILE_PATH}\n")
        
        prefixes = get_department_prefixes()
        print(f"Found {len(prefixes)} departments to scrape.\n")
        
        total_saved = scrape_departments(prefixes)
        
        print(f"\nDone! Successfully scraped {total_saved} total sections.")
    except Exception as e:
        print(f"Critical error: {e}")