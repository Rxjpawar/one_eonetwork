import os
import json
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio

load_dotenv()

EMAIL    = os.getenv("EON_EMAIL")
PASSWORD = os.getenv("EON_PASSWORD")

TARGET_URL = (
    "https://one.eonetwork.org/people"
)

OUTPUT_FILE  = "eon_all_profiles.json"
PROFILE_SEL  = 'a[href*="/page/profile?id="]'


# ── Helpers ──────────────────────────────────────────────────────────────────

async def login(page):
    print("[*] Navigating to EON login (Okta)...")
    await page.goto("https://one.eonetwork.org/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)

    await page.wait_for_selector('#username', timeout=15000)
    await page.click('#username')
    await page.fill('#username', EMAIL)
    await page.wait_for_timeout(600)

    btn = await page.wait_for_selector(
        '#okta-signin-submit, input[type="submit"], button[type="submit"]',
        timeout=5000
    )
    await btn.click()
    await page.wait_for_timeout(2000)

    try:
        await page.wait_for_selector('input[type="password"]', timeout=8000)
        await page.fill('input[type="password"]', PASSWORD)
        await page.wait_for_timeout(500)
        submit = await page.query_selector(
            '#okta-signin-submit, input[type="submit"], button[type="submit"]'
        )
        if submit:
            await submit.click()
        else:
            await page.keyboard.press("Enter")
    except PlaywrightTimeoutError:
        pass

    print("[*] Waiting for post-login redirect...")
    try:
        await page.wait_for_function(
            "() => !window.location.href.includes('/login')",
            timeout=25000
        )
        print(f"[+] Login successful! URL: {page.url}")
    except PlaywrightTimeoutError:
        input("    >>> Log in manually, then press ENTER: ")


async def debug_dump(page, label="debug"):
    """Save full-page screenshot, HTML, and all hrefs for inspection."""
    await page.screenshot(path=f"{label}_screenshot.png", full_page=True)
    print(f"  [debug] Screenshot : {label}_screenshot.png")

    content = await page.content()
    with open(f"{label}_page.html", "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [debug] HTML dump  : {label}_page.html")

    anchors = await page.query_selector_all("a[href]")
    hrefs = sorted({await a.get_attribute("href") for a in anchors} - {None})
    with open(f"{label}_links.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(hrefs))
    print(f"  [debug] {len(hrefs)} links  : {label}_links.txt")
    print(f"  [debug] Current URL: {page.url}")


async def collect_page_profiles(page):
    """Return {url: name} dict for all profiles on the current page."""
    anchors = await page.query_selector_all(PROFILE_SEL)
    profiles = {}
    for anchor in anchors:
        href = await anchor.get_attribute("href")
        name = (await anchor.inner_text()).strip()
        if href and "/page/profile?id=" in href:
            if href.startswith("/"):
                href = "https://one.eonetwork.org" + href
            profiles[href] = name
    return profiles


async def get_total_pages(page):
    try:
        btns = await page.query_selector_all('[aria-label^="Page "]')
        nums = []
        for btn in btns:
            lbl = await btn.get_attribute("aria-label")
            if lbl:
                try:
                    nums.append(int(lbl.replace("Page ", "").strip()))
                except ValueError:
                    pass
        return max(nums) if nums else 173
    except Exception:
        return 173


async def click_next_page(page):
    try:
        return await page.evaluate("""
            () => {
                for (const svg of document.querySelectorAll('svg.fa-angle-right')) {
                    const parent = svg.closest('[role="button"], button, a');
                    if (parent) { parent.click(); return true; }
                }
                return false;
            }
        """)
    except Exception as e:
        print(f"    [!] click_next_page error: {e}")
        return False


async def wait_for_page_change(page, prev_href, timeout=10000):
    try:
        await page.wait_for_function(
            f"""() => {{
                const links = document.querySelectorAll('a[href*="/page/profile?id="]');
                return links.length > 0 && links[0].getAttribute('href') !== '{prev_href}';
            }}""",
            timeout=timeout
        )
    except PlaywrightTimeoutError:
        await page.wait_for_timeout(2000)


# ── Navigation strategies ─────────────────────────────────────────────────────

async def navigate_to_directory(page):
    """
    Try multiple strategies to load the people directory.
    Returns True when PROFILE_SEL links are found on the page.
    """

    # Strategy 1: Direct URL, generous wait
    print("[*] Strategy 1: Direct URL navigation...")
    try:
        await page.goto(TARGET_URL, wait_until="load", timeout=60000)
    except PlaywrightTimeoutError:
        print("    Load timed out — continuing...")
    await page.wait_for_timeout(8000)

    count = await page.locator(PROFILE_SEL).count()
    print(f"    Profile links found: {count}")
    if count > 0:
        return True

    # Strategy 2: Reload
    print("[*] Strategy 2: Reloading...")
    try:
        await page.reload(wait_until="load", timeout=60000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(6000)

    count = await page.locator(PROFILE_SEL).count()
    print(f"    Profile links found: {count}")
    if count > 0:
        return True

    # Strategy 3: Go to /people without query params, wait, then apply full URL
    print("[*] Strategy 3: Land on /people first, then apply filters...")
    try:
        await page.goto("https://one.eonetwork.org/people", wait_until="load", timeout=30000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(4000)
    try:
        await page.goto(TARGET_URL, wait_until="load", timeout=60000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(6000)

    count = await page.locator(PROFILE_SEL).count()
    print(f"    Profile links found: {count}")
    if count > 0:
        return True

    # All strategies failed — dump debug info and ask user
    print("\n[!] All strategies failed. Dumping page state...")
    await debug_dump(page, "page1_debug")
    print("\n    The browser is open. Check the screenshot and links file.")
    print("    If profiles are visible in the browser window, press ENTER to try scraping anyway.")
    input("    >>> Press ENTER to continue: ")

    count = await page.locator(PROFILE_SEL).count()
    return count > 0


# ── Main scrape loop ──────────────────────────────────────────────────────────

async def scrape_all_pages(page):
    loaded = await navigate_to_directory(page)
    if not loaded:
        return {}

    if "/login" in page.url:
        print("[!] Redirected to login — session did not persist.")
        return {}

    total_pages = await get_total_pages(page)
    print(f"[+] Total pages detected: {total_pages}\n")

    all_profiles = {}
    current_page = 1

    while current_page <= total_pages:
        print(f"  [Page {current_page:>3}/{total_pages}]", end="  ")

        page_profiles = await collect_page_profiles(page)
        all_profiles.update(page_profiles)
        print(f"{len(page_profiles):>2} profiles  |  Total: {len(all_profiles)}")

        # Auto-save every 10 pages
        if current_page % 10 == 0:
            _save(all_profiles, OUTPUT_FILE)
            print(f"             [+] Progress auto-saved ({len(all_profiles)} profiles so far)")

        if current_page >= total_pages:
            break

        first = await page.query_selector(PROFILE_SEL)
        prev_href = (await first.get_attribute("href")) if first else ""

        if not await click_next_page(page):
            print(f"\n[!] Next button not found on page {current_page}. Stopping.")
            break

        await wait_for_page_change(page, prev_href)
        await page.wait_for_timeout(800)
        current_page += 1

    return all_profiles


def _save(profiles_dict, filename):
    profiles_list = [
        {"name": name, "url": url}
        for url, name in sorted(profiles_dict.items(), key=lambda x: x[1])
    ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"total_profiles": len(profiles_list), "profiles": profiles_list},
                  f, indent=2, ensure_ascii=False)


# ── Entry point ───────────────────────────────────────────────────────────────

async def get_urls():
    if not EMAIL or not PASSWORD:
        print("[!] Set EON_EMAIL and EON_PASSWORD in your .env file.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await login(page)
            all_profiles = await scrape_all_pages(page)

            if not all_profiles:
                print("\n[!] No profiles collected. Check debug files.")
            else:
                _save(all_profiles, OUTPUT_FILE)
                print(f"\n{'='*55}")
                print(f"  DONE! {len(all_profiles)} profiles saved → '{OUTPUT_FILE}'")
                print(f"{'='*55}")
                print("\n  Sample:")
                for url, name in list(all_profiles.items())[:5]:
                    print(f"  {name:35s}  {url}")

        except Exception as e:
            print(f"\n[!] Unexpected error: {e}")
            await page.screenshot(path="error_screenshot.png")
            print("[!] Screenshot saved: error_screenshot.png")

        finally:
            input("\n[*] Press ENTER to close the browser...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(get_urls())