
---

## 🛒 Grocery Scraper Dashboard — User Guide

This web application allows you to **search products across Asda, Co-op, and Ocado** using a single input field and view live scraping progress in real-time.

---

### ✅ 1. Requirements

Make sure you have the following installed:

* **Python 3.11**
* **Google Chrome** **Version 137.0.7151.69 (Official Build) (64-bit)**
* **ChromeDriver Version 137.0.7151.69** (Provided Driver)
* **Python packages:**

  ```bash
  pip install -r requirements.txt
  ```

---

### 📁 2. Folder Structure

Place the following files in the same directory:

```
/your-folder/
├── app.py                     ← Flask app (you created)
├── asda_scraper.py            ← Provided scraper
├── coop_scraper_v2.py         ← Provided scraper
├── ocado_scraper.py           ← Provided scraper
├── morrisons_scraper.py       ← Provided scraper
├── sainsburys_scraper.py      ← Provided scraper
├── tesco_scraper.py           ← Provided scraper
```

Ensure that the scrapers are set to accept `input()` for user queries (they already are).

---

### ▶️ 3. How to Run the App

Open a terminal in your project folder and run:

```bash
python app.py
```

You’ll see output like:

```
 * Running on http://127.0.0.1:5000 (Press CTRL+C to quit)
```

---

### 🌐 4. Using the Web Interface

1. Open your browser and go to:
   👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

2. Enter a product keyword in the search box (e.g., `"milk"` or `"coffee"`).

3. Click **“Run Scrapers”**.

4. You'll see live status updates like:

   * `▶️ Running Asda scraper...`
   * `[Asda] ✅ Accepted cookies.`
   * `[Ocado] 📦 Found 20 products on page 1`
   * `✅ Asda scraper Completed`
   * `🎉 All scrapers finished.`

---

### 📦 5. Output Files

Each scraper will save results as:

* `.csv` and `.xlsx` files
* File name format:
  `asda_milk_20250613.csv`, `coop_milk_20250613.xlsx`, etc.

Files are saved in the **same folder** where the script runs.

---

### ⚠️ 6. Notes & Troubleshooting

* **Headless Mode**: All scrapers run Chrome in headless mode (no visible browser window).
* **Timeouts**: If a scraper takes too long or crashes, the app will show an error in the log.
* **KeyboardInterrupt** (Ctrl+C): Will safely trigger emergency saves.
* **Ensure ChromeDriver is in your PATH** (or modify the scripts to point to the full path).

---

### 🧪 Example Run

Search term: `bread`
✔ Asda scraper found 80 items
✔ Co-op scraper found 32 items
✔ Ocado scraper found 122 items
📁 Files saved:

* `asda_bread_20250613.csv`
* `coop_bread_20250613.xlsx`
* `ocado_bread_20250613.csv`

---

