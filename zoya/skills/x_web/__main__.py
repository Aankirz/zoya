"""Owner login visit: `.venv/bin/python -m zoya.skills.x_web` opens Zoya's Chrome profile (D11) on
X, YouTube, Medium and MakeMyTrip through browser.py's own launch, waits for Enter, then closes
Chrome so the profile isn't locked when Zoya starts. Quit Zoya first (one Chrome per profile)."""

from zoya.tools import browser

LOGIN_PAGES = (
    "https://x.com/login",
    "https://accounts.google.com/",
    "https://medium.com/m/signin",
    "https://www.makemytrip.com",
)


def main() -> None:
    browser.warm()
    browser.goto(LOGIN_PAGES[0])
    for url in LOGIN_PAGES[1:]:
        browser.on_page(lambda page, url=url: page.context.new_page().goto(url))
    input("Sign in on every tab in Zoya's browser, then press Enter here… ")
    browser.on_page(lambda page: page.context.close())
    print("Closed Zoya's browser. You're set.")


if __name__ == "__main__":
    main()
