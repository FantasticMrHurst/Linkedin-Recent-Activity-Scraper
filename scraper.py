import os
import re
from datetime import datetime
from typing import List, Optional, Tuple

from playwright.sync_api import sync_playwright


def _number_from_label(label: Optional[str]) -> int:
    """Extract an integer count from an aria-label string."""
    if not label:
        return 0
    match = re.search(r"([\d,.]+)", label)
    if not match:
        return 0
    return int(match.group(1).replace(",", "").replace(".", ""))


def scrape_profile_posts(
    profile_url: str, storage_state_path: Optional[str] = None, headless: bool = True
) -> Tuple[str, List[dict]]:
    """
    Visit a LinkedIn profile and collect recent posts.

    Args:
        profile_url: Full URL to the LinkedIn profile.
        storage_state_path: Optional Playwright storage state file for authenticated sessions.
        headless: Whether to run the browser in headless mode.

    Returns:
        A tuple of profile name and a list of post dictionaries.
    """
    posts: List[dict] = []
    profile_name: str = ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context_kwargs = {}
        if storage_state_path and os.path.exists(storage_state_path):
            context_kwargs["storage_state"] = storage_state_path
        context = browser.new_context(**context_kwargs)
        page = context.new_page()

        page.goto(profile_url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        profile_name = (
            page.locator("h1.text-heading-xlarge, h1").first.text_content() or ""
        ).strip()

        # Load more posts by scrolling the page a few times.
        for _ in range(3):
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(1200)

        raw_posts = page.eval_on_selector_all(
            "article",
            """
            (articles) => articles.map(article => {
                const linkEl = article.querySelector('a[href*="/posts/"], a[href*="/updates/"]');
                const timeEl = article.querySelector('time');
                const reactionBtn = article.querySelector('button[aria-label*="reaction" i], button[aria-label*="like" i]');
                const commentBtn = article.querySelector('button[aria-label*="comment" i], a[aria-label*="comment" i]');
                const repostBtn = article.querySelector('button[aria-label*="repost" i], button[aria-label*="share" i]');
                return {
                    link: linkEl ? linkEl.href : null,
                    dateText: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent || '').trim() : null,
                    reactions: reactionBtn ? reactionBtn.getAttribute('aria-label') : null,
                    comments: commentBtn ? commentBtn.getAttribute('aria-label') : null,
                    reposts: repostBtn ? repostBtn.getAttribute('aria-label') : null,
                };
            })
            """,
        )

        for entry in raw_posts:
            post_url = entry.get("link")
            if not post_url:
                continue
            posts.append(
                {
                    "post_url": post_url.split("?")[0],
                    "posted_at": entry.get("dateText") or "",
                    "likes": _number_from_label(entry.get("reactions")),
                    "comments": _number_from_label(entry.get("comments")),
                    "reposts": _number_from_label(entry.get("reposts")),
                    "scraped_at": datetime.utcnow().isoformat(),
                }
            )

        browser.close()

    return profile_name or profile_url, posts
