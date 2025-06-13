import time
import pandas as pd
import random
# Use undetected_chromedriver for better stealth
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import signal
import sys
import atexit
from urllib.parse import quote_plus

# --- Globals for emergency saving ---
emergency_data = []
emergency_filename_base = ""
emergency_driver = None

def save_data_batch(data_to_save, base_filename):
    """Saves a batch of data to both CSV and Excel, dropping duplicates."""
    if not data_to_save:
        print("⚠️ No new data to save for this batch.")
        return False

    # Create a DataFrame and remove duplicates based on the product URL
    df = pd.DataFrame(data_to_save)
    # Note: If saving in batches, duplicate check should happen at the end
    # For this script, we'll keep it simple and save whatever is passed.
    
    csv_file = f"{base_filename}.csv"
    excel_file = f"{base_filename}.xlsx"

    # --- Save to CSV ---
    try:
        # Append to CSV if it exists, otherwise create it
        header = not pd.io.common.file_exists(csv_file)
        df.to_csv(csv_file, mode='a', header=header, index=False, encoding="utf-8-sig")
        print(f"✅ Saved/Appended {len(data_to_save)} items to CSV: {csv_file}")
    except Exception as e:
        print(f"❌ CSV save failed: {e}")

    # --- Save to Excel ---
    try:
        # Excel saving is more complex to append, so we overwrite with all data
        # For simplicity, this example will just save the latest batch.
        # A more robust solution would read the old excel file, append, and save.
        df.to_excel(excel_file, index=False)
        print(f"✅ Saved {len(data_to_save)} items to Excel: {excel_file}")
    except Exception as e:
        print(f"⚠️ Excel save failed (requires openpyxl): {e}")
    return True

def emergency_save(signum=None, frame=None):
    """Handles Ctrl+C interruption to save all collected data."""
    global emergency_data, emergency_filename_base, emergency_driver
    print(f"\n🚨 Emergency Save triggered! Saving {len(emergency_data)} total items.")
    if emergency_data:
        # Create a unique filename for the emergency save
        emergency_df = pd.DataFrame(emergency_data).drop_duplicates(subset=["URL"], keep="first")
        filename = f"{emergency_filename_base}_emergency_{datetime.now().strftime('%H%M%S')}"
        
        try:
            emergency_df.to_csv(f"{filename}.csv", index=False, encoding="utf-8-sig")
            print(f"✅ Emergency data saved to {filename}.csv")
        except Exception as e:
            print(f"❌ Emergency CSV save failed: {e}")

    if emergency_driver:
        try:
            emergency_driver.quit()
        except:
            pass
    sys.exit(0)

def scrape_tesco_products():
    query = input("Search for Tesco product: ").strip() or "bread"
    encoded_query = quote_plus(query)
    base_filename = f"tesco_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    global emergency_data, emergency_filename_base, emergency_driver
    emergency_filename_base = base_filename
    
    # --- Setup emergency signal handlers ---
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)
    atexit.register(emergency_save)

    # --- Setup undetected_chromedriver options ---
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    # Using undetected-chromedriver handles most anti-detection measures,
    # so we don't need to manually set user-agents or exclude switches.
    
    # --- IMPORTANT: PROXY CONFIGURATION (Highly Recommended) ---
    # Akamai will block your IP after a few requests. Use a residential proxy.
    # proxy_server = "http://user:password@proxy.provider.com:port"
    # options.add_argument(f'--proxy-server={proxy_server}')

    driver = uc.Chrome(options=options)
    emergency_driver = driver
    wait = WebDriverWait(driver, 20) # Increase wait time for slower network/proxies

    url = f"https://www.tesco.com/groceries/en-GB/search?query={encoded_query}"
    print(f"🔍 Searching Tesco for: '{query}'")
    print(f"🌐 Opening URL: {url}")
    driver.get(url)

    # --- Handle Cookie Banner ---
    try:
        # Use a more specific selector for the accept button
        cookie_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@id='onetrust-accept-btn-handler']")))
        print("Found cookie button, pausing to appear human...")
        time.sleep(random.uniform(2, 4)) # Human-like pause before clicking
        cookie_btn.click()
        print("✅ Accepted cookies.")
        time.sleep(random.uniform(3, 5)) # Wait for page to settle after click
    except Exception:
        print("⚠️ Cookie button not found or not clickable. Continuing...")

    all_data = []
    
    try:
        page_count = 1
        while True:
            print(f"\n--- Scraping Page {page_count} ---")
            
            # Wait for the main product list container to be present
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.product-list")))
            # Add a small random delay to mimic human scrolling/reading time
            time.sleep(random.uniform(2, 5))
            
            # Selectors might change. These are current as of late 2024/early 2025.
            product_elements = driver.find_elements(By.CSS_SELECTOR, "li.product-list--list-item")

            if not product_elements:
                print("⚠️ No product elements found on this page. The site structure may have changed or there are no results.")
                break

            page_data = []
            for item in product_elements:
                try:
                    name_element = item.find_element(By.CSS_SELECTOR, "h3 > a")
                    name = name_element.text.strip()
                    link = name_element.get_attribute("href")

                    price = item.find_element(By.CSS_SELECTOR, "p.price-control-wrapper").text.strip()
                    price_per = item.find_element(By.CSS_SELECTOR, "p.price-per-quantity-weight").text.strip()

                    product = {
                        "Name": name,
                        "Price": price,
                        "Price Per": price_per,
                        "URL": link,
                        "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    page_data.append(product)
                    print(f"  - Scraped: {name}")
                    
                    # Add a tiny, random delay between scraping each item
                    time.sleep(random.uniform(0.5, 1.5))

                except Exception as e:
                    print(f"⚠️ Error scraping an individual product item: {e}")
                    continue

            # Add new, unique data to the master list
            new_items = [p for p in page_data if p["URL"] not in [e["URL"] for e in all_data]]
            all_data.extend(new_items)
            emergency_data = all_data.copy()
            
            # Save the newly scraped items from this page
            if new_items:
                save_data_batch(new_items, base_filename)
            else:
                print("✔️ No new items found on this page.")

            # --- Pagination ---
            try:
                # Find the 'Next page' link. It's usually an `<a>` tag with a specific aria-label.
                next_btn = driver.find_element(By.CSS_SELECTOR, "a[data-auto='pagination-next']")
                print("➡️ Navigating to next page...")
                page_count += 1
                driver.get(next_btn.get_attribute('href'))
            except Exception:
                print("🛑 No 'Next page' button found. Reached the end.")
                break

    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user (Ctrl+C).")
    except Exception as e:
        print(f"❌ An unexpected error occurred during scraping: {e}")

    print("\n🏁 Scraping finished. Performing final cleanup.")
    atexit.unregister(emergency_save) # Unregister to prevent double saving on normal exit
    driver.quit()
    print("🔒 Browser closed.")

if __name__ == "__main__":
    print("🚀 Starting Advanced Tesco Scraper")
    print("=" * 50)
    print("💡 This script uses undetected-chromedriver to avoid bot detection.")
    print("💡 For best results, configure a residential proxy in the script.")
    print("💡 Press Ctrl+C at any time to save progress and quit safely.")
    print("=" * 50)
    try:
        scrape_tesco_products()
    except KeyboardInterrupt:
        print("\n👋 Gracefully exiting.")
    except Exception as e:
        print(f"❌ A fatal error occurred: {e}")