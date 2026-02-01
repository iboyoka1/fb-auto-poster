from playwright.sync_api import sync_playwright

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch()
        print("Playwright browser launched successfully")
        browser.close()
