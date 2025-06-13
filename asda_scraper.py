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

# Globals
emergency_data = []
emergency_filename_base = ""
emergency_driver = None

def save_data_batch(data_to_save, base_filename):
    if not data_to_save:
        print("No data to save.")
        return False

    df = pd.DataFrame(data_to_save).drop_duplicates(subset=["URL"])
    csv_filename = f"{base_filename}.csv"
    excel_filename = f"{base_filename}.xlsx"

    try:
        df.to_csv(csv_filename, mode='a', index=False, encoding='utf-8-sig', header=not pd.io.common.file_exists(csv_filename))
        print(f"Appended to CSV: {csv_filename}")
    except Exception as e:
        print(f"CSV save failed: {e}")

    try:
        if pd.io.common.file_exists(excel_filename):
            existing_df = pd.read_excel(excel_filename)
            df = pd.concat([existing_df, df]).drop_duplicates(subset=["URL"])
        df.to_excel(excel_filename, index=False)
        print(f"Updated Excel: {excel_filename}")
    except Exception as e:
        print(f"Excel save failed: {e}")
    return True

def emergency_save(signum=None, frame=None):
    global emergency_data, emergency_filename_base, emergency_driver
    print(f"\n Emergency Save: {len(emergency_data)} items.")
    if emergency_data:
        filename = f"{emergency_filename_base}_emergency_{datetime.now().strftime('%H%M%S')}"
        save_data_batch(emergency_data, filename)
    if emergency_driver:
        try:
            emergency_driver.quit()
        except:
            pass
    sys.exit(0)

def get_last_page(driver, wait):
    try:
        last_page_el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.asda-link.asda-link--primary.co-pagination__last-page")))
        last_page = int(last_page_el.text.strip())
        print(f"Last page detected: {last_page}")
        return last_page
    except:
        print("Could not detect last page. Defaulting to 1.")
        return 1

def scrape_page(driver, wait):
    products = []
    wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.co-item.co-item--rest-in-shelf")))
    time.sleep(2)

    product_elements = driver.find_elements(By.CSS_SELECTOR, "li.co-item.co-item--rest-in-shelf")
    for item in product_elements:
        try:
            name = item.find_element(By.CSS_SELECTOR, "h3.co-product__title a").text.strip()
            link = "https://groceries.asda.com" + item.find_element(By.CSS_SELECTOR, "h3.co-product__title a").get_attribute("href")
            price = item.find_element(By.CSS_SELECTOR, "strong.co-product__price").text.strip()
            price_per = item.find_element(By.CSS_SELECTOR, "span.co-product__price-per-uom").text.strip()

            products.append({
                "Name": name,
                "Price": price,
                "Unit Price": price_per,
                "URL": link,
                "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            time.sleep(1)
        except Exception as e:
            print(f"Error parsing item: {e}")
            continue
    return products

def scrape_asda_products():
    query = input("Search for: ").strip() or "milk"
    encoded_query = quote_plus(query)
    base_filename = f"asda_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    global emergency_data, emergency_filename_base, emergency_driver
    emergency_filename_base = base_filename
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)
    atexit.register(emergency_save)

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    driver = webdriver.Chrome(options=options)
    emergency_driver = driver
    wait = WebDriverWait(driver, 15)

    # Load first page to get total pages
    url = f"https://groceries.asda.com/search/{encoded_query}"
    driver.get(url)

    try:
        wait.until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        print("Accepted cookies.")
        time.sleep(5)
    except:
        print("Cookie button not shown or already accepted.")

    last_page = get_last_page(driver, wait)
    all_data = []

    for page in range(1, last_page + 1):
        paginated_url = f"https://groceries.asda.com/search/{encoded_query}/products?page={page}"
        print(f"\n Loading Page {page}/{last_page}: {paginated_url}")
        driver.get(paginated_url)
        time.sleep(5)

        try:
            page_data = scrape_page(driver, wait)
            print(f"Found {len(page_data)} products on page {page}")
            all_data.extend(page_data)
            emergency_data = all_data.copy()
            save_data_batch(page_data, base_filename)
        except Exception as e:
            print(f"Error scraping page {page}: {e}")
            continue

    atexit.unregister(emergency_save)
    driver.quit()
    print(f"Finished scraping {len(all_data)} total items.")

if __name__ == "__main__":
    print("ASDA Scraper with Pagination\nPress Ctrl+C to interrupt safely.\n")
    scrape_asda_products()
