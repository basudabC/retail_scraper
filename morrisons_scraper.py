import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import signal
import sys
import atexit
from urllib.parse import quote_plus

# Globals for emergency save
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


def scrape_morrisons_products():
    query = input("Search for Morrisons product: ").strip() or "milk"
    encoded_query = quote_plus(query)
    base_filename = f"morrisons_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

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

    url = f"https://groceries.morrisons.com/search?q={encoded_query}"
    print(f"Searching Morrisons for: {query}")
    print(f"Opening URL: {url}")
    driver.get(url)

    try:
        cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        cookie_btn.click()
        print("Accepted cookies.")
        time.sleep(6)
    except:
        print("Cookie button not found or already accepted.")

    all_data = []
    seen_urls = set()
    scroll_count = 0
    total_scraped = 0
    wait_time = 8

    def scroll_and_scrape():
        nonlocal scroll_count, wait_time, total_scraped
        scroll_count += 1
        print(f"Scroll #{scroll_count}")
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(wait_time)

        try:
            wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.product-card-container")))
        except TimeoutException:
            print("Timeout waiting for products, stopping.")
            return False

        product_elements = driver.find_elements(By.CSS_SELECTOR, "div.product-card-container")
        page_data = []

        for item in product_elements:
            try:
                name = item.find_element(By.CSS_SELECTOR, "h3[data-test='fop-title']").text.strip()
                price = item.find_element(By.CSS_SELECTOR, "span[data-test='fop-price']").text.strip()
                unit_price = item.find_element(By.CSS_SELECTOR, "span[data-test='fop-price-per-unit']").text.strip()
                rel_link = item.find_element(By.CSS_SELECTOR, "a[data-test='fop-product-link']").get_attribute("href")
                url = f"https://groceries.morrisons.com{rel_link}" if rel_link.startswith("/products") else rel_link

                if url in seen_urls:
                    continue

                product = {
                    "Name": name,
                    "Price": price,
                    "Unit Price": unit_price,
                    "URL": url,
                    "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                page_data.append(product)
                all_data.append(product)
                seen_urls.add(url)
            except Exception as e:
                print(f"Error scraping product: {e}")

        if page_data:
            emergency_data[:] = all_data
            print(f" Scroll #{scroll_count} scraped {len(page_data)} new products (Total: {len(all_data)})")
            total_scraped += len(page_data)
            return True
        else:
            print(f"No new products found at Scroll #{scroll_count}, stopping.")
            return False

        wait_time *= 1.5

    while True:
        if not scroll_and_scrape():
            break

    print(" Final save...")
    save_data_batch(all_data, base_filename, final=True)
    atexit.unregister(emergency_save)
    driver.quit()
    print(" Browser closed.")


if __name__ == "__main__":
    print("Starting Morrisons Scraper")
    print("=" * 50)
    print("Ctrl+C anytime to save and quit safely.")
    print("Data saves per scroll to CSV/Excel.")
    print("=" * 50)
    try:
        scrape_morrisons_products()
    except KeyboardInterrupt:
        print("Gracefully exiting.")
    except Exception as e:
        print(f" Fatal error: {e}")
