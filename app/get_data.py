import os
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

EON_EMAIL = os.getenv("EON_EMAIL")
EON_PASSWORD = os.getenv("EON_PASSWORD")


def fetch_profile_text(profile_url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        # Step 1: Load the profile page to trigger login
        url = profile_url
        #"https://one.eonetwork.org/page/profile?id={profile_id}
        page.goto(url, timeout=60000)
        page.wait_for_load_state("load")

        # Step 2: Login if redirected
        if "login" in page.url or "signin" in page.url or page.query_selector("input[type='password']"):
            print(f"[INFO] Logging in as {EON_EMAIL} ...")
            page.wait_for_selector("input[name='username']", timeout=15000)
            page.query_selector("input[name='username']").fill(EON_EMAIL)
            page.query_selector("input[type='password']").fill(EON_PASSWORD)
            submit_btn = page.query_selector("button[type='submit'], input[type='submit']")
            if submit_btn:
                submit_btn.click()
            else:
                page.query_selector("input[type='password']").press("Enter")
            page.wait_for_load_state("load", timeout=30000)
            page.wait_for_timeout(3000)
            print(f"[INFO] Post-login URL: {page.url}")

            # Step 3: Navigate to the profile page
            page.goto(url, timeout=60000)
            page.wait_for_load_state("load")

        # Step 4: Dismiss cookie banner
        try:
            accept_btn = page.wait_for_selector("button:has-text('Accept')", timeout=5000)
            if accept_btn:
                accept_btn.click()
                print("[INFO] Dismissed cookie banner")
        except Exception:
            pass

        # Step 5: Extract the iframe src containing the JWT token
        print("[INFO] Extracting altiframe iframe URL...")
        page.wait_for_timeout(3000)

        iframe_src = page.evaluate("""
            () => {
                const iframe = document.querySelector('#iframeProfilePage iframe');
                return iframe ? iframe.src : null;
            }
        """)

        if not iframe_src:
            # Fallback: parse from HTML
            html = page.content()
            match = re.search(r'src="(https://altiframe\.eonetwork\.org/ProfileDetails\?[^"]+)"', html)
            iframe_src = match.group(1) if match else None

        if not iframe_src:
            print("[ERROR] Could not find altiframe iframe src")
            browser.close()
            return ""

        print(f"[INFO] Found iframe URL: {iframe_src[:100]}...")

        # Step 6: Open the iframe URL directly in a new page (shares the same cookies/session)
        profile_page = context.new_page()
        profile_page.goto(iframe_src, timeout=60000)
        profile_page.wait_for_load_state("load")

        # Step 7: Wait for content to render (no "Loading..." spinner)
        print("[INFO] Waiting for profile iframe content...")
        for i in range(30):
            body_text = profile_page.inner_text("body")
            if "Loading" not in body_text and len(body_text.strip()) > 100:
                print(f"[INFO] Content loaded after ~{i+1}s")
                break
            profile_page.wait_for_timeout(1000)

        profile_page.wait_for_timeout(2000)
        text = profile_page.inner_text("body")

        browser.close()
        return text.strip()