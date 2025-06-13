import time
import pandas as pd
from datetime import datetime
import signal
import sys
import atexit
from urllib.parse import quote_plus
import warnings
import os
import re

import undetected_chromedriver as uc
# Patch Chrome class destructor to avoid WinError 6
uc.Chrome.__del__ = lambda self: None

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException

warnings.filterwarnings("ignore", category=ResourceWarning)

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
        except Exception as e:
            print(f"Error during emergency driver quit: {e}")
    sys.exit(0)

def get_current_page_number(driver):
    """Extract current page number from URL or pagination elements"""
    try:
        # Method 1: Check URL for page parameter
        current_url = driver.current_url
        if 'page=' in current_url:
            page_match = re.search(r'page=(\d+)', current_url)
            if page_match:
                return int(page_match.group(1))
        
        # Method 2: Check pagination elements (quick check only)
        try:
            current_page_elem = driver.find_element(By.CSS_SELECTOR, "li.ln-c-pagination__item--current span")
            return int(current_page_elem.text.strip())
        except:
            pass
            
        return None
    except Exception as e:
        print(f"Error getting page number: {e}")
        return None

def scrape_sainsburys_products():
    query = input("Search for Sainsbury's product: ").strip() or "milk"
    encoded_query = quote_plus(query)
    base_filename = f"sainsburys_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}"

    global emergency_data, emergency_filename_base, emergency_driver
    emergency_filename_base = base_filename
    signal.signal(signal.SIGINT, emergency_save)
    signal.signal(signal.SIGTERM, emergency_save)
    atexit.register(emergency_save)

    options = uc.ChromeOptions()
    #options.add_argument("--headless=new")  # Modern headless mode
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-images")  # Speed optimization
    options.add_argument("--disable-javascript")  # Only if site works without JS

    driver = uc.Chrome(options=options, headless=False)
    emergency_driver = driver
    wait = WebDriverWait(driver, 15)  # Reduced timeout

    all_data = []
    seen_urls = set()
    page_count = 1
    consecutive_failures = 0
    max_consecutive_failures = 3

    # Start with page 1
    url = f"https://www.sainsburys.co.uk/gol-ui/SearchResults/{encoded_query}"
    print(f"Searching Sainsbury's for: {query}")
    print(f"Opening URL: {url}")
    driver.get(url)

    try:
        cookie_btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler")))
        cookie_btn.click()
        print("Accepted cookies.")
        time.sleep(2)  # Reduced wait time
    except:
        print("Cookie button not found or already accepted.")

    def check_for_error_and_retry():
        """Check for error page and click Try again button if found"""
        try:
            try_again_button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="error-button"]')
            if try_again_button.is_displayed():
                print("Found 'Try again' button - clicking to retry...")
                driver.execute_script("arguments[0].click();", try_again_button)
                time.sleep(3)  # Reduced wait time
                return True
        except NoSuchElementException:
            pass
        except Exception as e:
            print(f"Error checking for retry button: {e}")
        return False

    def scrape_current_page():
        nonlocal all_data, consecutive_failures
        current_page_num = get_current_page_number(driver)
        print(f"Scraping page {page_count} (detected page: {current_page_num})...")
        
        # Start timing for 5-second check
        scrape_start_time = time.time()
        
        try:
            # Primary selector (most common)
            primary_selector = "div.pt__wrapper-inner"
            
            # Try primary selector first with shorter timeout
            products = None
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, primary_selector)))
                products = driver.find_elements(By.CSS_SELECTOR, primary_selector)
                if products:
                    print(f"Found {len(products)} products using selector: {primary_selector}")
                else:
                    print("Primary selector found elements but list is empty")
            except TimeoutException:
                # Check if 5 seconds have passed since we started scraping this page
                elapsed_time = time.time() - scrape_start_time
                if elapsed_time >= 5:
                    print(f"5+ seconds elapsed ({elapsed_time:.1f}s) without finding products - checking for errors...")
                    if check_for_error_and_retry():
                        print("Retried after error - attempting to scrape again...")
                        time.sleep(2)
                        # Try primary selector again after retry
                        try:
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, primary_selector)))
                            products = driver.find_elements(By.CSS_SELECTOR, primary_selector)
                            if products:
                                print(f"Found {len(products)} products after retry using primary selector")
                        except TimeoutException:
                            pass
                
                # If primary selector failed, try fallback selectors
                if not products:
                    fallback_selectors = [
                        "div[data-test-id='product-tile']",
                        ".pt__wrapper",
                        "[data-testid='product-tile']"
                    ]
                    
                    for selector in fallback_selectors:
                        try:
                            WebDriverWait(driver, 3).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            products = driver.find_elements(By.CSS_SELECTOR, selector)
                            if products:
                                print(f"Found {len(products)} products using fallback selector: {selector}")
                                break
                        except TimeoutException:
                            continue
            
            if not products:
                print("No product containers found with any selector")
                consecutive_failures += 1
                return 0
                
        except Exception as e:
            print(f"Error waiting for products: {e}")
            elapsed_time = time.time() - scrape_start_time
            if elapsed_time >= 5:
                print(f"5+ seconds elapsed ({elapsed_time:.1f}s) - checking for errors...")
                if check_for_error_and_retry():
                    print("Retried after error - attempting to scrape again...")
                    time.sleep(2)
                    try:
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pt__wrapper-inner")))
                        products = driver.find_elements(By.CSS_SELECTOR, "div.pt__wrapper-inner")
                        if products:
                            print(f"Found {len(products)} products after retry")
                        else:
                            consecutive_failures += 1
                            return 0
                    except Exception as retry_e:
                        print(f"Error even after retry: {retry_e}")
                        consecutive_failures += 1
                        return 0
                else:
                    consecutive_failures += 1
                    return 0
            else:
                consecutive_failures += 1
                return 0

        scraped_count = 0
        
        for i, product in enumerate(products):
            try:
                # Optimized selectors - try most common first
                name_elem = None
                url = None
                
                # Primary name selector
                try:
                    name_elem = product.find_element(By.CSS_SELECTOR, "h2.pt__info__description a")
                    name = name_elem.text.strip()
                    url = name_elem.get_attribute("href").strip()
                except:
                    # Fallback selectors
                    fallback_name_selectors = [
                        "a[data-test-id='product-tile-description']",
                        ".pt__info__description a",
                        "h3 a",
                        "a[title]"
                    ]
                    
                    for selector in fallback_name_selectors:
                        try:
                            name_elem = product.find_element(By.CSS_SELECTOR, selector)
                            name = name_elem.text.strip()
                            url = name_elem.get_attribute("href").strip()
                            if name and url:
                                break
                        except:
                            continue
                
                if not name or not url:
                    continue
                
                # Optimized price extraction
                price = "N/A"
                try:
                    price = product.find_element(By.CSS_SELECTOR, "span.pt__cost__retail-price").text.strip()
                except:
                    try:
                        price = product.find_element(By.CSS_SELECTOR, "[data-test-id='product-tile-price']").text.strip()
                    except:
                        pass
                
                # Optimized unit price extraction
                unit_price = "N/A"
                try:
                    unit_price = product.find_element(By.CSS_SELECTOR, "span.pt__cost__unit-price-per-measure").text.strip()
                except:
                    try:
                        unit_price = product.find_element(By.CSS_SELECTOR, "[data-test-id='product-tile-unit-price']").text.strip()
                    except:
                        pass

                if url in seen_urls:
                    continue

                data = {
                    "Name": name,
                    "Price": price,
                    "Unit Price": unit_price,
                    "URL": url,
                    "Page": page_count,
                    "Scraped At": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                all_data.append(data)
                emergency_data[:] = all_data
                seen_urls.add(url)
                scraped_count += 1
                
            except Exception as e:
                print(f"Error scraping product {i+1}: {e}")
                continue
        
        if scraped_count > 0:
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            
        print(f"Scraped {scraped_count} products from page {page_count}")
        return scraped_count

    def has_next_page():
        """Check if there's a next page button available"""
        try:
            # Primary next page selector
            try:
                next_button = driver.find_element(By.CSS_SELECTOR, "li.ln-c-pagination__item.ln-c-pagination__item--next a")
                if next_button.is_enabled() and next_button.is_displayed():
                    parent = next_button.find_element(By.XPATH, "..")
                    if "disabled" not in parent.get_attribute("class").lower():
                        return True
            except:
                # Fallback selectors
                fallback_selectors = [
                    "a[aria-label*='Next']",
                    ".ln-c-pagination__item--next a",
                    "a[title*='Next']"
                ]
                
                for selector in fallback_selectors:
                    try:
                        next_button = driver.find_element(By.CSS_SELECTOR, selector)
                        if next_button.is_enabled() and next_button.is_displayed():
                            parent = next_button.find_element(By.XPATH, "..")
                            if "disabled" not in parent.get_attribute("class").lower():
                                return True
                    except:
                        continue
            
            return False
        except Exception as e:
            print(f"Error checking next page: {e}")
            return False

    def click_next_page():
        """Click the next page button and wait for page to load"""
        try:
            current_url_before = driver.current_url
            
            # Find and click next button (optimized)
            next_button = None
            try:
                next_button = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "li.ln-c-pagination__item.ln-c-pagination__item--next a"))
                )
            except:
                # Fallback selectors
                fallback_selectors = [
                    "a[aria-label*='Next']",
                    ".ln-c-pagination__item--next a"
                ]
                
                for selector in fallback_selectors:
                    try:
                        next_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                        break
                    except:
                        continue
            
            if not next_button:
                print("No next button found")
                return False
            
            # Click using JavaScript to avoid interception
            driver.execute_script("arguments[0].click();", next_button)
            print("Next page clicked. Waiting for new content...")
            
            # Optimized page change detection
            max_wait_time = 10  # Reduced from 20
            start_time = time.time()
            
            while time.time() - start_time < max_wait_time:
                time.sleep(1)  # Reduced check interval
                
                try:
                    # Check if URL changed (most reliable)
                    current_url = driver.current_url
                    if current_url != current_url_before:
                        print("URL changed, page loaded")
                        time.sleep(1)  # Brief wait for content to settle
                        return True
                    
                    # Quick check for new products
                    try:
                        WebDriverWait(driver, 1).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.pt__wrapper-inner")))
                        time.sleep(1)  # Brief wait for content to settle
                        return True
                    except:
                        pass
                        
                except Exception as e:
                    print(f"Error during page change detection: {e}")
                    time.sleep(1)
            
            print("Page change not detected within timeout, but continuing...")
            time.sleep(2)  # Give it a bit more time
            return True
            
        except Exception as e:
            print(f"Error clicking next page: {e}")
            return False

    # Main scraping loop
    while True:
        scraped_count = scrape_current_page()
        
        # Check for consecutive failures
        if consecutive_failures >= max_consecutive_failures:
            print(f"Too many consecutive failures ({consecutive_failures}), stopping.")
            break
        
        if scraped_count == 0:
            print("No products found on current page.")
            if consecutive_failures >= 2:
                print("Multiple pages with no products, likely reached end.")
                break
        
        # Check if there's a next page
        if not has_next_page():
            print("No more pages available.")
            break
        
        # Save partial results every 5 pages
        if page_count % 5 == 0:
            print(f"Saving partial results after page {page_count}...")
            save_data_batch(all_data, f"{base_filename}_page_{page_count}", final=False)
        
        # Try to go to next page
        if not click_next_page():
            print("Failed to navigate to next page, stopping.")
            break
        
        page_count += 1
        
        # Reduced delay between pages
        time.sleep(1)  # Reduced from 3
        
        # Safety check to prevent infinite loops
        if page_count > 100:
            print("Reached maximum page limit, stopping.")
            break

    print(f"\nScraping completed! Total pages: {page_count}")
    print(f"Total unique products found: {len(all_data)}")
    print("Final save...")
    save_data_batch(all_data, base_filename, final=True)
    atexit.unregister(emergency_save)

    try:
        driver.quit()
    except Exception as e:
        print(f"Error while quitting driver: {e}")
    print("Browser closed.")

# Suppress stderr (as last-resort to silence undetected-chromedriver exit noise)
def suppress_stderr():
    sys.stderr = open(os.devnull, 'w')

atexit.register(suppress_stderr)

if __name__ == "__main__":
    print("Starting Sainsbury's Scraper (Optimized)")
    print("=" * 50)
    print("Ctrl+C anytime to save and quit safely.")
    print("Data saves to CSV and Excel.")
    print("Partial saves every 5 pages.")
    print("=" * 50)
    try:
        scrape_sainsburys_products()
    except KeyboardInterrupt:
        print("Gracefully exiting.")
    except Exception as e:
        print(f"Fatal error: {e}")
        emergency_save()