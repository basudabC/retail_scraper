import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import os
from datetime import datetime
import signal
import sys
import atexit

# Global variables for emergency save
emergency_data = []
emergency_filename_base = ""
emergency_driver = None

def save_data_batch(data_to_save, base_filename):
    """
    Saves a batch of data to both CSV and Excel files.
    It prioritizes saving to CSV. The function returns True if at least one format is saved.
    """
    if not data_to_save:
        print("No data to save.")
        return False

    print(f"\n Attempting to save {len(data_to_save)} products...")
    # Create a DataFrame and remove duplicates based on URL, keeping the first entry
    df = pd.DataFrame(data_to_save)
    df = df.drop_duplicates(subset=['URL'], keep='first')

    # Define filenames
    csv_filename = f"{base_filename}.csv"
    excel_filename = f"{base_filename}.xlsx"

    csv_saved = False
    excel_saved = False

    # --- Save to CSV (Primary) ---
    try:
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig') # utf-8-sig for better Excel compatibility
        print(f"Successfully saved {len(df)} products to CSV: {csv_filename}")
        csv_saved = True
    except Exception as e:
        print(f"CRITICAL: Error saving to CSV: {e}")

    # --- Save to Excel (Secondary) ---
    try:
        # This requires the 'openpyxl' library to be installed: pip install openpyxl
        import openpyxl
        df.to_excel(excel_filename, index=False)
        print(f"Successfully saved {len(df)} products to Excel: {excel_filename}")
        excel_saved = True
    except ImportError:
        # This is just a warning, not a script-breaking failure.
        print("Excel library (openpyxl) not found. Skipping Excel save. To enable, run: pip install openpyxl")
    except Exception as e:
        print(f"Error saving to Excel: {e}")

    # Return True if the primary format (CSV) or the secondary format (Excel) was saved
    return csv_saved or excel_saved


def emergency_save(signum=None, frame=None):
    """Emergency save function for interruptions (e.g., Ctrl+C)."""
    global emergency_data, emergency_filename_base, emergency_driver
    
    print(f"INTERRUPTION DETECTED! Performing emergency save for {len(emergency_data)} products...")
    
    if emergency_data and emergency_filename_base:
        # Create a uniquely named file for the emergency save to avoid overwriting a good file
        emergency_base_file = f"{emergency_filename_base}_emergency_{datetime.now().strftime('%H%M%S')}"
        save_data_batch(emergency_data, emergency_base_file)
    else:
        print("No data in memory to save.")
    
    # Close driver safely
    if emergency_driver:
        try:
            emergency_driver.quit()
            print("Browser closed safely.")
        except:
            pass
    
    print("Script terminated. Check for saved files!")
    sys.exit(0)


def scrape_ocado_products():
    # Get user input for search query
    query = input("Enter your search query: ").strip()
    if not query:
        query = "bread"  # Default fallback
        print(f"No query entered. Using default query: '{query}'")
    
    # Create a base filename (without extension) for all save operations
    base_output_file = f"ocado_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"
    
    # Setup global variables for emergency save
    global emergency_data, emergency_filename_base, emergency_driver
    emergency_filename_base = base_output_file
    
    # Register emergency save handlers
    signal.signal(signal.SIGINT, emergency_save)  # Handles Ctrl+C
    signal.signal(signal.SIGTERM, emergency_save) # Handles termination
    atexit.register(emergency_save)              # Handles normal or unexpected script exit
    
    # Setup browser
    options = Options()
    #options.add_argument("--start-maximized")
    options.add_argument("--headless")  # Run the browser in the background
    options.add_argument("--window-size=1920,1080")  # Set a larger window size for the headless browser
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    emergency_driver = driver  # Set global reference for emergency cleanup
    wait = WebDriverWait(driver, 15)

    url = f"https://www.ocado.com/search?entry={query}"
    print(f"Searching for: {query}")
    print(f"Opening URL: {url}")
    driver.get(url)

    # Accept cookies
    try:
        cookie_button = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        cookie_button.click()
        print("Accepted cookies.")
    except TimeoutException:
        print("Cookie button not found or already accepted.")
    
    print("Waiting 7.5 seconds for the site to load...")
    time.sleep(7.5)

    all_products_data = []
    scroll_count = 0
    max_scrolls_per_cycle = 20
    last_saved_count = 0
    
    try:
        while True:
            print(f"Starting scroll cycle {scroll_count // max_scrolls_per_cycle + 1}")
            
            # Update emergency data continuously
            emergency_data = all_products_data.copy()
            
            # Perform scrolling and data collection
            for scroll in range(max_scrolls_per_cycle):
                scroll_count += 1
                print(f"Scroll {scroll + 1}/{max_scrolls_per_cycle} (Total: {scroll_count})")
                
                driver.execute_script("window.scrollBy(0, window.innerHeight/3);")
                time.sleep(4)
                
                current_products = scrape_current_products(driver, wait, scroll_count, all_products_data)
                
                # Add new products, avoiding duplicates by checking the URL
                existing_urls = {p['URL'] for p in all_products_data}
                new_products = [p for p in current_products if p['URL'] not in existing_urls]
                if new_products:
                    all_products_data.extend(new_products)
                    print(f"--> Found {len(new_products)} new products. Total: {len(all_products_data)}")
                
                # Update emergency data with the latest products
                emergency_data = all_products_data.copy()
                
                # Check if we have a new batch of 20 products to save
                current_count = len(all_products_data)
                if current_count >= last_saved_count + 20:
                    products_to_save_count = (current_count // 20) * 20
                    
                    success = save_data_batch(all_products_data[:products_to_save_count], base_output_file)
                    if success:
                        last_saved_count = products_to_save_count
                        print(f"Progress: {last_saved_count} products saved. {current_count - last_saved_count} pending next batch.")
                    else:
                        print(f"Batch save failed. Data remains in memory. Will retry on next trigger.")
            
            # After a scroll cycle, check for a "Show more" button
            print("Looking for 'Show more' button...")
            try:
                show_more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-primary.show-more")))
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", show_more_button)
                time.sleep(3)
                
                show_more_button.click()
                print("Clicked 'Show more' button.")
                print(" Waiting 5 seconds for new products to load...")
                time.sleep(5)
                
            except TimeoutException:
                print(" No more 'Show more' buttons found. All products are loaded.")
                break # Exit the main while loop
            except Exception as e:
                print(f" Error clicking 'Show more' button: {e}")
                break # Exit on error

    except KeyboardInterrupt:
        # The atexit handler will automatically call emergency_save
        print(f"\n Scraping interrupted by user! Initiating emergency save...")
    except Exception as e:
        print(f"\n An unexpected error occurred: {e}")
        # The atexit handler will automatically call emergency_save

    # Final save operation to catch any remaining products
    print("\n Scraping process finished. Performing final save.")
    if all_products_data:
        success = save_data_batch(all_products_data, base_output_file)
        if success:
            print(f" Scraping completed successfully! Total unique products scraped: {len(all_products_data)}")
            print(f" Data saved to {base_output_file}.csv (and .xlsx if possible).")
        else:
            print(f"\n Final save failed. Check logs for errors. Emergency save might have created a backup.")
    else:
        print(" No products were scraped.")

    # Clean up
    atexit.unregister(emergency_save) # Unregister to prevent double-saving on normal exit
    emergency_driver = None
    driver.quit()
    print(" Browser closed successfully.")


def scrape_current_products(driver, wait, scroll_num, all_products_data):
    """Scrape products currently visible on the page."""
    products_on_page = []
    try:
        product_elements = driver.find_elements(By.CSS_SELECTOR, "li.fops-item.fops-item--cluster")
        
        for product_element in product_elements:
            try:
                # Scrape essential data first to check for existence
                product_url = safe_get_attribute(product_element, ".fop-contentWrapper > a", "href", "N/A", wait_time=0.5)
                
                # Check if this product URL has already been processed to avoid redundant scraping
                existing_urls = {p['URL'] for p in all_products_data}
                if product_url in existing_urls:
                    continue
                    
                # Scrape the rest of the data
                name = safe_get_text(product_element, ".fop-title span:first-child", "N/A")
                title = safe_get_attribute(product_element, ".fop-dietary span", "title", "N/A")
                weight = safe_get_text(product_element, ".fop-catch-weight", "N/A")
                price = safe_get_text(product_element, ".fop-price", "N/A")
                unit_price = safe_get_text(product_element, ".fop-unit-price", "N/A")
                review = safe_get_attribute(product_element, ".fop-rating-inner", "title", "No reviews")
                review_count = safe_get_text(product_element, ".fop-rating__count", "N/A")
                shelf_life = safe_get_text(product_element, ".fop-life", "N/A")
                promo = safe_get_text(product_element, ".fop-row-promo span", "N/A")
                
                if name != "N/A" and product_url != "N/A":
                    products_on_page.append({
                        "Name": name,
                        "URL": product_url,
                        "Title": title,
                        "Weight": weight,
                        "Price": price,
                        "Unit Price": unit_price,
                        "Review": review,
                        "Review Count": review_count,
                        "Shelf Life": shelf_life,
                        "Promo": promo,
                        "Scraped_at_Scroll": scroll_num,
                        "Scraped_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                
            except Exception as e:
                print(f" Error scraping an individual product: {e}")
                continue
                
    except Exception as e:
        print(f" Error finding product elements on page: {e}")
    
    return products_on_page

def safe_get_text(parent_element, selector, default="N/A", wait_time=1.5):
    """Safely get text from a child element."""
    try:
        element = parent_element.find_element(By.CSS_SELECTOR, selector)
        return element.text.strip() if element.text and element.text.strip() else default
    except NoSuchElementException:
        return default

def safe_get_attribute(parent_element, selector, attribute, default="N/A", wait_time=1.5):
    """Safely get an attribute from a child element."""
    try:
        element = parent_element.find_element(By.CSS_SELECTOR, selector)
        attr_value = element.get_attribute(attribute)
        return attr_value.strip() if attr_value and attr_value.strip() else default
    except NoSuchElementException:
        return default


if __name__ == "__main__":
    print(" Starting Enhanced Ocado Scraper")
    print("=" * 50)
    print(" Press Ctrl+C at any time to safely interrupt and save your data.")
    print(" Data is saved in batches of 20 to both CSV and Excel (if available).")
    print("=" * 50)
    
    try:
        scrape_ocado_products()
    except KeyboardInterrupt:
        # emergency_save is registered with atexit, so it will be called automatically.
        print("\n Script interrupted by user. Gracefully shutting down.")
    except Exception as e:
        # emergency_save will also handle this.
        print(f"\n A critical error in the main block forced the script to stop: {e}")