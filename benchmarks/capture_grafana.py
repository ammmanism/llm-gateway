"""Capture the provisioned Grafana dashboard with Chromium.

Full-page capture breaks Grafana's scene layout (panels render into a
composited layer that full_page screenshots miss), so this uses a tall
viewport instead.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

URL = (
    "http://localhost:3000/d/llm-gateway-evidence/llm-gateway-evidence"
    "?orgId=1&from=now-15m&to=now&kiosk&refresh=5s"
)
OUTPUT = Path("docs/evidence/figures/grafana_dashboard.png")


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=["--disable-gpu", "--force-color-profile=srgb"]
        )
        page = browser.new_page(viewport={"width": 1680, "height": 1720})
        page.goto(URL, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_selector("text=Request rate", timeout=120_000)
        page.wait_for_timeout(8_000)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(OUTPUT), full_page=False)
        browser.close()
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
