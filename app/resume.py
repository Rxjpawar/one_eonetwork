import os
import json
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio

load_dotenv()

EMAIL       = os.getenv("EON_EMAIL")
PASSWORD    = os.getenv("EON_PASSWORD")
TARGET_URL  = "https://one.eonetwork.org/people"
OUTPUT_FILE = "eon_all_profiles2.json"
PROFILE_SEL = 'a[href*="/page/profile?id="]'

# Refresh browser context every N pages to prevent memory crash
REFRESH_EVERY = 10


# ── Login ─────────────────────────────────────────────────────────────────────

async def login(page):
    print("[*] Logging in...")
    await page.goto("https://one.eonetwork.org/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(4000)

    # Wait for username field via JS polling
    for _ in range(20):
        found = await page.evaluate("() => !!document.querySelector('#username')")
        if found:
            break
        await page.wait_for_timeout(1000)

    await page.evaluate(f"() => {{ const el = document.querySelector('#username'); if(el) el.value = ''; }}")
    await page.type('#username', EMAIL, delay=80)
    await page.wait_for_timeout(500)

    # Click submit/next button
    await page.evaluate("""
        () => {
            const btn = document.querySelector(
                '#okta-signin-submit, input[type="submit"], button[type="submit"]'
            );
            if (btn) btn.click();
        }
    """)
    await page.wait_for_timeout(2500)

    # Wait for password field
    for _ in range(10):
        found = await page.evaluate("() => !!document.querySelector('input[type=\"password\"]')")
        if found:
            break
        await page.wait_for_timeout(1000)

    pw_found = await page.evaluate("() => !!document.querySelector('input[type=\"password\"]')")
    if pw_found:
        await page.evaluate(f"() => {{ const el = document.querySelector('input[type=\"password\"]'); if(el) el.value = ''; }}")
        await page.type('input[type="password"]', PASSWORD, delay=80)
        await page.wait_for_timeout(500)
        await page.evaluate("""
            () => {
                const btn = document.querySelector(
                    '#okta-signin-submit, input[type="submit"], button[type="submit"]'
                );
                if (btn) btn.click();
            }
        """)

    try:
        await page.wait_for_function(
            "() => !window.location.href.includes('/login')",
            timeout=25000
        )
        print(f"[+] Logged in: {page.url}")
    except PlaywrightTimeoutError:
        input(">>> Log in manually then press ENTER: ")


# ── All DOM access via JS evaluate (no Python query_selector loops) ───────────

JUNK_NAMES = {"favorite users", "go to profile", "see all", "load more", ""}

async def collect_page_profiles(page):
    """Single JS call — no Python-side ElementHandle loops."""
    try:
        results = await page.evaluate("""
            () => {
                const out = [];
                document.querySelectorAll('a[href*="/page/profile?id="]').forEach(a => {
                    out.push({ href: a.getAttribute('href'), name: a.innerText.trim() });
                });
                return out;
            }
        """)
        profiles = {}
        for r in results:
            href = r.get("href", "")
            name = r.get("name", "").strip()
            # Skip junk entries
            if not href or name.lower() in JUNK_NAMES:
                continue
            if href.startswith("/"):
                href = "https://one.eonetwork.org" + href
            profiles[href] = name
        return profiles
    except Exception as e:
        print(f"    [!] collect_page_profiles error: {e}")
        return {}


async def get_total_pages(page):
    try:
        result = await page.evaluate("""
            () => {
                let max = 1;
                document.querySelectorAll('[aria-label^="Page "]').forEach(b => {
                    const n = parseInt((b.getAttribute('aria-label') || '').replace('Page ', ''));
                    if (!isNaN(n) && n > max) max = n;
                });
                return max;
            }
        """)
        return result if result > 1 else 1163
    except Exception:
        return 1163


async def click_next_page(page):
    try:
        # Strategy 1: click parent of fa-angle-right SVG
        clicked = await page.evaluate("""
            () => {
                for (const svg of document.querySelectorAll('svg.fa-angle-right')) {
                    const p = svg.closest('[role="button"], button, a');
                    if (p) { p.click(); return true; }
                }
                return false;
            }
        """)
        if clicked:
            return True

        # Strategy 2: aria-label next button
        clicked = await page.evaluate("""
            () => {
                const btn = document.querySelector(
                    '[aria-label="Go to next page"], [aria-label="Next page"], [aria-label="next"]'
                );
                if (btn) { btn.click(); return true; }
                return false;
            }
        """)
        if clicked:
            return True

        # Strategy 3: find last page-number button and click the element after it
        clicked = await page.evaluate("""
            () => {
                const btns = Array.from(document.querySelectorAll('[role="button"]'));
                // Find currently active page button and click the next sibling
                for (let i = 0; i < btns.length; i++) {
                    if (btns[i].getAttribute('aria-current') === 'true' && btns[i+1]) {
                        btns[i+1].click();
                        return true;
                    }
                }
                return false;
            }
        """)
        return clicked

    except Exception as e:
        print(f"    [!] click_next_page error: {e}")
        return False


async def get_first_profile_href(page):
    try:
        return await page.evaluate("""
            () => {
                const el = document.querySelector('a[href*="/page/profile?id="]');
                return el ? el.getAttribute('href') : '';
            }
        """)
    except Exception:
        return ""


async def wait_for_page_change(page, prev_href, timeout=12000):
    safe = prev_href.replace("'", "\\'")
    try:
        await page.wait_for_function(
            f"""() => {{
                const el = document.querySelector('a[href*="/page/profile?id="]');
                return el && el.getAttribute('href') !== '{safe}';
            }}""",
            timeout=timeout
        )
    except PlaywrightTimeoutError:
        await page.wait_for_timeout(2500)


async def profile_count(page):
    try:
        return await page.evaluate(
            "() => document.querySelectorAll('a[href*=\"/page/profile?id=\"]').length"
        )
    except Exception:
        return 0


# ── Navigate to a specific page number ───────────────────────────────────────

async def navigate_to_page(page, page_number):
    """
    Navigate to a specific page number by loading the directory
    and clicking the page number button directly.
    Falls back to URL param as last resort.
    """
    # First load the base directory
    try:
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    except PlaywrightTimeoutError:
        pass

    # Wait for profiles and pagination to render
    for _ in range(10):
        await page.wait_for_timeout(2000)
        cnt = await profile_count(page)
        if cnt >= 5:
            break

    if page_number <= 1:
        return await profile_count(page) > 0

    # Try clicking the exact page number button
    clicked = await page.evaluate(f"""
        () => {{
            const btns = document.querySelectorAll('[aria-label^="Page "]');
            for (const btn of btns) {{
                const lbl = btn.getAttribute('aria-label') || '';
                if (lbl.trim() === 'Page {page_number}') {{
                    btn.click();
                    return true;
                }}
            }}
            return false;
        }}
    """)

    if clicked:
        await page.wait_for_timeout(3000)
        return await profile_count(page) > 0

    # Fallback: click last visible page button then use next arrow to reach target
    # This handles cases where the exact page button isn't in the pagination strip
    print(f"    [~] Page {page_number} button not visible, navigating via last page + next...")

    # Click the highest visible page number first
    await page.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('[aria-label^="Page "]'));
            let max = null, maxN = 0;
            for (const btn of btns) {
                const n = parseInt((btn.getAttribute('aria-label') || '').replace('Page ', ''));
                if (!isNaN(n) && n > maxN) { maxN = n; max = btn; }
            }
            if (max) max.click();
        }
    """)
    await page.wait_for_timeout(2000)

    # Now click next until we reach target page
    current = await page.evaluate("""
        () => {
            const active = document.querySelector('[aria-current="true"], [aria-current="page"]');
            if (active) return parseInt(active.innerText.trim()) || 0;
            return 0;
        }
    """)

    while current < page_number:
        prev_href = await get_first_profile_href(page)
        clicked = await click_next_page(page)
        if not clicked:
            break
        await wait_for_page_change(page, prev_href, timeout=8000)
        current += 1

    return await profile_count(page) > 0


# ── Fresh page creation (context reuse, new tab) ──────────────────────────────

async def fresh_page(context):
    """Close all existing pages and open a new clean one."""
    for p in context.pages:
        try:
            await p.close()
        except Exception:
            pass
    return await context.new_page()


# ── Load progress ─────────────────────────────────────────────────────────────

def load_progress():
    """Load existing profiles and determine resume page."""
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            profiles = {p["url"]: p["name"] for p in data.get("profiles", [])}
            last_page = data.get("last_page", 1)
            # last_page=0 means fully completed — start fresh
            resume = last_page if last_page > 1 else 1
            print(f"[+] Resuming from page {resume} ({len(profiles)} profiles already saved)")
            return profiles, resume
        except Exception as e:
            print(f"[!] Could not load progress: {e}")
    return {}, 1
    return {}, 1


def _save(profiles_dict, filename, last_page=1):
    # Merge with any existing profiles already on disk to never lose data
    existing = {}
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            existing = {p["url"]: p["name"] for p in data.get("profiles", [])}
        except Exception:
            pass
    merged = {**existing, **profiles_dict}  # new data wins on conflict
    profiles_list = [
        {"name": name, "url": url}
        for url, name in sorted(merged.items(), key=lambda x: x[1])
    ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            {"total_profiles": len(profiles_list), "last_page": last_page, "profiles": profiles_list},
            f, indent=2, ensure_ascii=False
        )


# ── Main scrape loop ──────────────────────────────────────────────────────────

async def scrape_all_pages(browser, context, start_page=1, existing_profiles=None):
    all_profiles = dict(existing_profiles) if existing_profiles else {}
    current_page = 1  # Always click through from page 1 — EON doesn't support URL page jumps
    print(f"[+] Starting with {len(all_profiles)} existing profiles in memory.")

    # Open first page and login
    page = await context.new_page()
    await login(page)

    # Navigate to directory
    print("[*] Loading people directory...")
    try:
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
    except PlaywrightTimeoutError:
        pass
    await page.wait_for_timeout(5000)

    # If resuming mid-way, jump to correct page via URL param
    if start_page > 1:
        print(f"[*] Jumping to resume page {start_page}...")
        ok = await navigate_to_page(page, start_page)
        if not ok:
            print(f"[!] Could not jump to page {start_page}, starting from 1")
            current_page = 1

    # Wait until at least 5 profiles are visible (poll every 2s, up to 20s)
    print("[*] Waiting for member list to fully render...")
    for tick in range(10):
        await page.wait_for_timeout(2000)
        cnt = await profile_count(page)
        print(f"    [{(tick+1)*2}s] profiles visible: {cnt}")
        if cnt >= 5:
            break

    if await profile_count(page) < 2:
        print("[!] Member list did not load. Trying reload...")
        try:
            await page.reload(wait_until="domcontentloaded", timeout=45000)
        except PlaywrightTimeoutError:
            pass
        await page.wait_for_timeout(8000)

    if await profile_count(page) == 0:
        print("[!] No profiles found on directory page.")
        return all_profiles

    total_pages = await get_total_pages(page)
    print(f"[+] Total pages: {total_pages} | Starting from page: {current_page}\n")

    while current_page <= total_pages:
        try:
            print(f"  [Page {current_page:>4}/{total_pages}]", end="  ")

            # Collect profiles on this page
            page_profiles = await collect_page_profiles(page)
            all_profiles.update(page_profiles)
            print(f"{len(page_profiles):>2} profiles  |  Total: {len(all_profiles)}")

            # Auto-save every 10 pages with last_page marker
            if current_page % 10 == 0:
                _save(all_profiles, OUTPUT_FILE, last_page=current_page)
                print(f"             [+] Auto-saved at page {current_page} ({len(all_profiles)} profiles)")

            if current_page >= total_pages:
                break

            # ── Periodic reload every REFRESH_EVERY pages to clear memory ──
            if current_page % REFRESH_EVERY == 0:
                print(f"\n  [~] Reloading page at {current_page} to clear memory...")
                _save(all_profiles, OUTPUT_FILE, last_page=current_page + 1)

                try:
                    await page.reload(wait_until="domcontentloaded", timeout=45000)
                except PlaywrightTimeoutError:
                    pass

                # Wait for profiles to re-render
                for _ in range(10):
                    await page.wait_for_timeout(2000)
                    if await profile_count(page) >= 5:
                        break

                cnt = await profile_count(page)
                print(f"  [~] Reloaded — {cnt} profiles visible on page {current_page}\n")

            # Get current first href before clicking next
            prev_href = await get_first_profile_href(page)

            if not await click_next_page(page):
                print(f"\n[!] Next button not found on page {current_page}. Stopping.")
                break

            await wait_for_page_change(page, prev_href)
            await page.wait_for_timeout(400)
            current_page += 1

        except Exception as e:
            print(f"\n[!] Error on page {current_page}: {e}")
            _save(all_profiles, OUTPUT_FILE, last_page=current_page)
            print(f"    Saved progress. Re-run script to resume from page {current_page}.")
            break

    return all_profiles


# ── Entry point ───────────────────────────────────────────────────────────────

async def get_urls():
    if not EMAIL or not PASSWORD:
        print("[!] Set EON_EMAIL and EON_PASSWORD in .env")
        return

    # Resume from last saved progress
    existing_profiles, start_page = load_progress()

    # ── One-time override: force resume from a specific page ──────────────
    # Remove or comment this out after the run completes successfully
    FORCE_RESUME_PAGE = 0
    if FORCE_RESUME_PAGE > 1 and start_page < FORCE_RESUME_PAGE:
        print(f"[*] Forcing resume from page {FORCE_RESUME_PAGE}")
        start_page = FORCE_RESUME_PAGE

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=30,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )

        try:
            all_profiles = await scrape_all_pages(
                browser, context,
                start_page=start_page,
                existing_profiles=existing_profiles
            )

            if not all_profiles:
                print("\n[!] No profiles collected.")
            else:
                _save(all_profiles, OUTPUT_FILE, last_page=0)
                print(f"\n{'='*55}")
                print(f"  DONE! {len(all_profiles)} profiles → '{OUTPUT_FILE}'")
                print(f"{'='*55}")
                for url, name in list(all_profiles.items())[:5]:
                    print(f"  {name:35s}  {url}")

        except Exception as e:
            print(f"\n[!] Fatal error: {e}")

        finally:
            input("\n[*] Press ENTER to close browser...")
            await browser.close()


if __name__ == "__main__":
    asyncio.run(get_urls())