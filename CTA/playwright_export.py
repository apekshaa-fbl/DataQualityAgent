"""
QuickSight CSV Exporter — Playwright automation.

Logs into QuickSight, opens the Master Customers analysis,
exports to CSV from the table visual, and saves to ~/Downloads.

Env vars required:
    QUICKSIGHT_ACCOUNT    — QuickSight account name (e.g. firmable-dashboards)
    QUICKSIGHT_USERNAME   — QuickSight login email
    QUICKSIGHT_PASSWORD   — QuickSight login password

Returns the path to the downloaded CSV file.
"""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger(__name__)

ANALYSIS_URL = "https://ap-southeast-2.quicksight.aws.amazon.com/sn/account/firmable-dashboards/analyses/master-customers-sf/sheets/sheet-master"
DOWNLOADS_DIR = Path.home() / "Downloads"


def export_csv(headless: bool = True) -> str:
    """
    Log in to QuickSight, export Master Customers table to CSV.
    Returns the path to the downloaded file.
    """
    from playwright.sync_api import sync_playwright

    account  = os.getenv("QUICKSIGHT_ACCOUNT")
    username = os.getenv("QUICKSIGHT_USERNAME")
    password = os.getenv("QUICKSIGHT_PASSWORD")

    if not all([account, username, password]):
        raise ValueError("QUICKSIGHT_ACCOUNT, QUICKSIGHT_USERNAME and QUICKSIGHT_PASSWORD must be set in .env")

    before = set(DOWNLOADS_DIR.glob("Master_Customers_*.csv"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # 2560px wide so the visual-menu button (at x~2280) is on-screen
        page = browser.new_page(viewport={"width": 2560, "height": 1080})

        # ── Step 1: Login (3-step: account → username → AWS SSO password) ──────
        logger.info("Navigating to QuickSight login...")
        page.goto("https://ap-southeast-2.quicksight.aws.amazon.com/", timeout=30000)
        page.wait_for_load_state("networkidle", timeout=15000)

        page.locator("#account-name-input").fill(account)
        page.locator("button[type=submit]").first.click()
        page.wait_for_selector("#username-input", timeout=15000)

        page.locator("#username-input").fill(username)
        page.locator("button[type=submit]").first.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        page.wait_for_timeout(2000)

        page.locator("#awsui-input-0").fill(password)
        page.locator('button:has-text("Sign in")').click()
        page.wait_for_url("**/start**", timeout=30000)
        page.wait_for_timeout(2000)
        logger.info("Logged in.")

        # ── Step 2: Open analysis ──────────────────────────────────────────────
        logger.info("Opening Master Customers analysis...")
        page.goto(ANALYSIS_URL, timeout=60000, wait_until="load")
        page.wait_for_timeout(15000)
        logger.info(f"Analysis loaded: {page.title()}")

        # ── Step 3: Click the visual three-dot menu ────────────────────────────
        logger.info("Clicking visual context menu...")
        menu_pos = page.evaluate("""
            () => {
                const menus = document.querySelectorAll('[class*="visual-menu"]');
                const main = Array.from(menus).find(el => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && el.tagName === 'DIV'
                        && r.x > 500
                        && !el.className.includes('below')
                        && !el.className.includes('above')
                        && !el.className.includes('resize');
                });
                if (!main) return null;
                const r = main.getBoundingClientRect();
                return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }
        """)
        if not menu_pos:
            raise RuntimeError("Could not find visual-menu button on the analysis page.")

        page.mouse.click(menu_pos["x"], menu_pos["y"])
        page.wait_for_timeout(1500)

        # ── Step 4: Click "Export to CSV" ─────────────────────────────────────
        logger.info("Selecting Export to CSV...")
        page.locator('text="Export to CSV"').first.wait_for(state="visible", timeout=10000)
        page.locator('text="Export to CSV"').first.click()
        page.wait_for_timeout(3000)

        # ── Step 5: Open Exports panel ────────────────────────────────────────
        page.locator('text="File"').first.click()
        page.wait_for_timeout(800)
        page.locator('text="Exports"').first.click()

        # Wait for export to complete (up to 60s)
        logger.info("Waiting for export to complete...")
        page.locator('text="Your CSV is ready."').wait_for(state="visible", timeout=60000)
        logger.info("CSV ready. Downloading...")

        # ── Step 6: Download ──────────────────────────────────────────────────
        with page.expect_download(timeout=30000) as dl_info:
            page.locator('text="Click to download"').first.click()

        download = dl_info.value
        dest = DOWNLOADS_DIR / download.suggested_filename
        download.save_as(str(dest))
        logger.info(f"Saved to: {dest}")

        browser.close()

    return str(dest)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    path = export_csv(headless=False)
    print(f"\nExported: {path}")
