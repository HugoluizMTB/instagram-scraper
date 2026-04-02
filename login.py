# !! ALWAYS USE A SECONDARY ACCOUNT — NEVER YOUR PERSONAL ACCOUNT !!
# Instagram may restrict or ban accounts used for scraping.

import base64
import json
import re

from config import BASE_DIR, INSTAGRAM_PASSWORD, INSTAGRAM_USERNAME


PROFILE_DIR = BASE_DIR / ".browser_profile"


def login():
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("\n[ERROR] Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in your .env file first.")
        print("        cp .env.example .env && edit .env")
        return

    print("\n" + "=" * 60)
    print("  !! WARNING: USE A SECONDARY ACCOUNT, NOT YOUR MAIN !!")
    print("  Instagram may restrict accounts used for scraping.")
    print("=" * 60)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        print("\n[INFO] Opening browser...")

        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            channel="chrome",
            viewport={"width": 1280, "height": 720},
        )

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Check if already logged in from a previous run
        page.goto("https://www.instagram.com/", timeout=30000)
        page.wait_for_timeout(5000)

        cookies = ctx.cookies("https://www.instagram.com")
        cookie_names = {c["name"] for c in cookies}

        if {"sessionid", "csrftoken", "ds_user_id"}.issubset(cookie_names):
            print("[INFO] Already logged in from a previous session!")
        else:
            print("[INFO] Navigating to login page...")
            page.goto("https://www.instagram.com/accounts/login/", timeout=30000)
            page.wait_for_timeout(5000)

            # Dismiss consent dialogs
            for text in [
                "Allow essential and optional cookies",
                "Allow all cookies",
                "Permitir cookies essenciais e opcionais",
                "Permitir todos os cookies",
                "Accept", "Allow", "Permitir", "Aceitar",
            ]:
                try:
                    btn = page.get_by_text(text, exact=True)
                    if btn.is_visible(timeout=1000):
                        btn.click()
                        print(f"[INFO] Dismissed consent dialog.")
                        page.wait_for_timeout(3000)
                        break
                except Exception:
                    pass

            # Fill login
            try:
                page.wait_for_selector("input[name='username']", timeout=15000)
                page.fill("input[name='username']", INSTAGRAM_USERNAME)
                page.wait_for_timeout(500)
                page.fill("input[name='password']", INSTAGRAM_PASSWORD)
                page.wait_for_timeout(500)
                page.click("button[type='submit']")
                print("[INFO] Credentials submitted. Waiting for login...")
                page.wait_for_timeout(8000)
            except Exception as e:
                print(f"[INFO] Auto-fill failed ({e}). Log in manually in the browser.")

        # Wait for user to handle CAPTCHA/2FA if needed
        while True:
            cookies = ctx.cookies("https://www.instagram.com")
            cookie_names = {c["name"] for c in cookies}
            required = {"sessionid", "csrftoken", "ds_user_id"}
            missing = required - cookie_names

            if not missing:
                break

            print(f"\n[WAITING] Login not complete yet. Missing: {missing}")
            input("          Handle CAPTCHA/2FA in the browser, then press ENTER: ")
            page.wait_for_timeout(2000)

        cookies_json = json.dumps(cookies, ensure_ascii=False)
        cookies_b64 = base64.b64encode(cookies_json.encode()).decode()
        _update_env("INSTAGRAM_COOKIES", cookies_b64)

        print(f"\n[OK] Session saved to .env (INSTAGRAM_COOKIES)")
        print(f"     Cookies captured: {len(cookies)}")
        print(f"     Session expires in ~90 days. Re-run login.py to renew.")

        ctx.close()


def _update_env(key: str, value: str):
    env_path = BASE_DIR / ".env"

    if env_path.exists():
        content = env_path.read_text()
        pattern = rf"^{re.escape(key)}=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
        else:
            content = content.rstrip() + f"\n{key}={value}\n"
    else:
        content = f"{key}={value}\n"

    env_path.write_text(content)


if __name__ == "__main__":
    login()
