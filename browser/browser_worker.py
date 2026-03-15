"""
Playwright subprocess for browser automation.
Runs as a separate subprocess from the main bot.
Does not import aiogram and does not participate in async event loop.

Usage:
    python browser/browser_worker.py --task luma_book --params '{"url":"...","form_data":{...}}'
"""

import argparse
import json
import sys

from playwright.sync_api import sync_playwright


def book_luma(url: str, form_data: dict) -> dict:
    """Register for Luma event via Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(2000)

            # Click Register / RSVP
            register_btn = page.locator(
                "button:has-text('Register'), button:has-text('RSVP')"
            )
            if register_btn.count() == 0:
                return {
                    "status": "failed",
                    "error": "Register button not found",
                }
            register_btn.first.click()
            page.wait_for_timeout(1000)

            # Fill form
            for field_name, value in form_data.items():
                selector = (
                    f"input[name='{field_name}'], "
                    f"input[placeholder*='{field_name}']"
                )
                field = page.locator(selector)
                if field.count() > 0:
                    field.first.fill(str(value))

            # Submit
            submit_btn = page.locator(
                "button[type='submit'], "
                "button:has-text('Submit'), "
                "button:has-text('Confirm')"
            )
            if submit_btn.count() > 0:
                submit_btn.first.click()
                page.wait_for_timeout(3000)

            # Check result
            page_text = page.text_content("body") or ""
            if "confirmed" in page_text.lower() or "registered" in page_text.lower():
                return {"status": "confirmed"}
            elif "waitlist" in page_text.lower():
                return {"status": "waitlisted"}
            else:
                return {"status": "unknown", "page_text": page_text[:500]}

        except Exception as e:
            return {"status": "failed", "error": str(e)}
        finally:
            browser.close()


def book_meetup(url: str, form_data: dict) -> dict:
    """RSVP on Meetup via Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(2000)

            attend_btn = page.locator(
                "button:has-text('Attend'), button:has-text('RSVP')"
            )
            if attend_btn.count() == 0:
                return {
                    "status": "failed",
                    "error": "Attend button not found",
                }
            attend_btn.first.click()
            page.wait_for_timeout(3000)

            page_text = page.text_content("body") or ""
            if "going" in page_text.lower() or "rsvp" in page_text.lower():
                return {"status": "confirmed"}
            else:
                return {"status": "unknown", "page_text": page_text[:500]}

        except Exception as e:
            return {"status": "failed", "error": str(e)}
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task", required=True, choices=["luma_book", "meetup_book"]
    )
    parser.add_argument("--params", required=True)
    args = parser.parse_args()

    params = json.loads(args.params)

    if args.task == "luma_book":
        result = book_luma(params["url"], params["form_data"])
    elif args.task == "meetup_book":
        result = book_meetup(params["url"], params["form_data"])
    else:
        result = {"status": "failed", "error": f"Unknown task: {args.task}"}

    print(json.dumps(result))
    sys.exit(0 if result["status"] != "failed" else 1)


if __name__ == "__main__":
    main()
