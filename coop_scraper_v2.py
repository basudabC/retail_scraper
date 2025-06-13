
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import signal
import sys
import atexit
from urllib.parse import quote_plus

emergency_data = []
emergency_filename_base = ""
emergency_driver = None

def save_data_batch(data_to_save, base_filename, final=False):
    if not data_to_save:
        print("No data to save.")
        return False

    df = pd.DataFrame(data_to_save).drop_duplicates(subset=["URL"], keep="first")
    csv_file = f"{base_filename}.csv" if final else f"{base_filename}_partial.csv"
    excel_file = f"{base_filename}.xlsx" if final else f"{base_filename}_partial.xlsx"

    try:
        df.to_csv(csv_file, index=False, encoding="utf-8-sig")
        print(f" Saved CSV: {csv_file}")
    except Exception as e:
        print(f"CSV save failed: {e}")

    try:
        import openpyxl
        df.to_excel(excel_file, index=False)
        print(f" Saved Excel: {excel_file}")
    except Exception as e:
        print(f" Excel save failed: {e}")
    return True

def emergency_save(signum=None, frame=None):
    global emergency_data, emergency_filename_base, emergency_driver
    print(f"Emergency Save: {len(emergency_data)} items.")
    if emergency_data:
        filename = f"{emergency_filename_base}_emergency"
        save_data_batch(emergency_data, filename, final=True)
    if emergency_driver:
        try:
            emergency_driver.quit()
        except:
            pass
    sys.exit(0)

def scrape_coop_products():
    query = input("Search for Co-op product: ").strip() or "milk"
    encoded_query = quote_plus(query)
    base_filename = f"coop_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    global emergency_data, emergency_filename_base, emergency_driver
    emergency_filename_base = base_filename
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)
    atexit.register(emergency_save)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    emergency_driver = driver
    wait = WebDriverWait(driver, 15)

    url = f"https://www.coop.co.uk/search?query={encoded_query}"
    print(f"Searching Co-op for: {query}")
    print(f"Opening URL: {url}")
    driver.get(url)

    try:
        wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        print("Accepted cookies.")
        time.sleep(3)
    except:
        print("Cookie button not found or already accepted.")

    all_data = []
    seen_urls = set()

    def scrape_search_results():
        nonlocal all_data
        items = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.search-results-list__item")))
        for item in items:
            try:
                title_el = item.find_element(By.CSS_SELECTOR, "a.search-result__title")
                name = title_el.text.strip()
                url = title_el.get_attribute("href")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                try:
                    price = "N/A"
                    unit_price = "N/A"
                    image = item.find_element(By.CSS_SELECTOR, "img").get_attribute("src").strip()
                    description = item.find_element(By.CSS_SELECTOR, "p.coop-t-font-size-18").text.strip()
                except Exception as e:
                    print(f"Optional field missing: {e}")
                    continue

                all_data.append({
                    "Name": name,
                    "URL": url,
                    "Price": price,
                    "Unit Price": unit_price,
                    "Description": description,
                    "Image": image,
                    "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                emergency_data[:] = all_data
            except Exception as e:
                print(f"Error scraping item: {e}")

    while True:
        scrape_search_results()
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "a.pagination--next")
            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(1)
            next_button.click()
            print("Clicked next page...")
            time.sleep(3)
        except:
            print("No more pages.")
            break

    print("Final save...")
    save_data_batch(all_data, base_filename, final=True)
    atexit.unregister(emergency_save)
    driver.quit()
    print("Browser closed.")

if __name__ == "__main__":
    print("Starting Co-op Flat Scraper")
    print("=" * 50)
    print("Ctrl+C anytime to save and quit safely.")
    print("Data saves to CSV/Excel.")
    print("=" * 50)
    try:
        scrape_coop_products()
    except KeyboardInterrupt:
        print("Gracefully exiting.")
    except Exception as e:
        print(f"Fatal error: {e}")
        emergency_save()
