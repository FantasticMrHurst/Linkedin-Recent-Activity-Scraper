## LinkedIn Recent Activity Scraper

This project is a minimal Flask app that scrapes LinkedIn profile posts daily (and on-demand) and stores them in a SQLite database.

### Features
- Add LinkedIn profile URLs to monitor.
- Daily background scrape via APScheduler.
- Manual **Check Now** button to trigger scraping immediately.
- Stores profile name, post link, date text, like count, comment count, and repost count.

### Setup
1. Install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```
2. (Optional) Provide an authenticated Playwright storage state if the profile requires login:
   - Log in once with Playwright and save state to `playwright_state.json`, or supply your own path via the `PLAYWRIGHT_STORAGE` environment variable.
3. Run the app:
   ```bash
   flask --app app run
   ```
   The scheduler starts automatically and will scrape all saved profiles once per day.

### Environment variables
- `SCRAPER_DB_PATH`: Path to the SQLite database (default `app.db`).
- `PLAYWRIGHT_STORAGE`: Path to a Playwright storage state JSON file for authenticated scraping (default `playwright_state.json`).
- `FLASK_SECRET_KEY`: Secret key for session/flash messages (default development value).

### Notes
- LinkedIn may require an authenticated session to view full activity. Supply a storage state file with valid cookies for reliable scraping.
- The scraper uses general selectors (`article` elements and accessibility labels) to extract counts. If LinkedIn updates their markup, selectors may need adjustments.
