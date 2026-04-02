import base64
import json
import logging
import random
import re
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from config import (
    DELAY_BETWEEN_POSTS,
    INSTAGRAM_COOKIES,
    MAX_DAYS,
    MAX_DELAY_SECONDS,
    MAX_POSTS_PER_PROFILE,
    MAX_PROFILES_PER_RUN,
    MAX_SESSION_MINUTES,
    MIN_DELAY_SECONDS,
    SAFE_HOUR_END,
    SAFE_HOUR_START,
)
from models import ScrapedPost, ScrapingProfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("instagram")


def _load_cookies() -> list[dict] | None:
    if not INSTAGRAM_COOKIES:
        return None
    try:
        decoded = base64.b64decode(INSTAGRAM_COOKIES).decode()
        return json.loads(decoded)
    except Exception as e:
        log.error(f"Failed to decode INSTAGRAM_COOKIES: {e}")
        return None


def _save_cookies_to_env(cookies: list[dict]):
    import re as _re
    from config import BASE_DIR

    cookies_json = json.dumps(cookies, ensure_ascii=False)
    cookies_b64 = base64.b64encode(cookies_json.encode()).decode()

    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return

    content = env_path.read_text()
    pattern = r"^INSTAGRAM_COOKIES=.*$"
    if _re.search(pattern, content, _re.MULTILINE):
        content = _re.sub(pattern, f"INSTAGRAM_COOKIES={cookies_b64}", content, flags=_re.MULTILINE)
    else:
        content = content.rstrip() + f"\nINSTAGRAM_COOKIES={cookies_b64}\n"
    env_path.write_text(content)


def scrape_instagram(db: Session) -> int:
    cookies = _load_cookies()
    if not cookies:
        log.error("No session found. Run `python login.py` first.")
        return 0

    from playwright.sync_api import sync_playwright

    hour = datetime.now().hour
    if hour < SAFE_HOUR_START or hour >= SAFE_HOUR_END:
        log.warning(f"Outside safe hours ({SAFE_HOUR_START}h-{SAFE_HOUR_END}h). Skipping.")
        return 0

    total = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            ctx = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
                locale="pt-BR",
                viewport={"width": 1280, "height": 720},
            )
            ctx.add_cookies(cookies)
            page = ctx.new_page()
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            profiles = _get_profiles(db)
            profiles = profiles[:MAX_PROFILES_PER_RUN]
            random.shuffle(profiles)
            session_start = time.time()

            for i, (username, display_name) in enumerate(profiles):
                elapsed = (time.time() - session_start) / 60
                if elapsed > MAX_SESSION_MINUTES:
                    log.warning(f"Session limit ({MAX_SESSION_MINUTES}min). Stopped at {i}/{len(profiles)}.")
                    break

                try:
                    posts = _scrape_profile_with_comments(page, username)
                    saved = _save_posts(db, username, posts)
                    _update_profile_stats(db, username, saved)
                    db.commit()
                    total += saved
                    log.info(f"@{username}: {saved} new posts")
                    time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))
                except Exception as e:
                    log.error(f"@{username}: {e}")
                    db.rollback()
                    time.sleep(random.uniform(10, 20))

            updated = ctx.cookies()
            _save_cookies_to_env(updated)

            browser.close()
    except Exception as e:
        log.error(f"Playwright error: {e}")

    log.info(f"Done. {total} new posts saved.")
    return total


def _get_profiles(db: Session) -> list[tuple[str, str]]:
    db_profiles = (
        db.execute(
            select(ScrapingProfile)
            .where(ScrapingProfile.is_active == True)  # noqa: E712
            .order_by(ScrapingProfile.priority.desc())
        )
        .scalars()
        .all()
    )

    if not db_profiles:
        log.warning("No profiles configured. Use `python cli.py add <username> <name>` to add profiles.")
        return []

    return [(p.username, p.display_name) for p in db_profiles]


def _update_profile_stats(db: Session, username: str, new_posts: int):
    profile = db.execute(
        select(ScrapingProfile).where(ScrapingProfile.username == username)
    ).scalar_one_or_none()
    if profile:
        profile.last_scraped_at = datetime.now(timezone.utc)
        profile.post_count = (profile.post_count or 0) + new_posts


def _scrape_profile_with_comments(page, username: str) -> list[dict]:
    page.goto(
        f"https://www.instagram.com/{username}/",
        wait_until="domcontentloaded",
        timeout=20000,
    )
    page.wait_for_timeout(random.uniform(3000, 5000))

    title = page.title()
    if "disponível" in title.lower() or "not available" in title.lower():
        log.warning(f"@{username}: profile not available")
        return []

    post_links = page.query_selector_all("a[href*='/p/']")
    hrefs = list(
        dict.fromkeys(
            [l.get_attribute("href") for l in post_links if l.get_attribute("href")]
        )
    )[:MAX_POSTS_PER_PROFILE]

    posts = []
    cutoff = datetime.now(timezone.utc).timestamp() - (MAX_DAYS * 86400)

    for href in hrefs:
        try:
            full_url = (
                f"https://www.instagram.com{href}" if href.startswith("/") else href
            )
            page.goto(full_url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(random.uniform(3000, 5000))

            post_date = _extract_date(page)
            if post_date:
                try:
                    ts = datetime.fromisoformat(
                        post_date.replace("Z", "+00:00")
                    ).timestamp()
                    if ts < cutoff:
                        break
                except (ValueError, TypeError):
                    pass

            caption = ""
            article = page.query_selector("article, [role='presentation'], main")
            if article:
                spans = page.query_selector_all(
                    "article span[dir='auto'], main span[dir='auto']"
                )
                for span in spans:
                    txt = span.inner_text().strip()
                    if len(txt) > 30:
                        caption = txt[:2000]
                        break

            if not caption:
                img = page.query_selector("article img")
                if img:
                    caption = (img.get_attribute("alt") or "")[:2000]

            if not caption:
                continue

            comments = _extract_comments(page)
            likes = _extract_likes(page)

            img_el = page.query_selector(
                "article img[src*='instagram'], article img[src*='cdninstagram']"
            )
            image_url = img_el.get_attribute("src") if img_el else ""

            posts.append(
                {
                    "caption": caption,
                    "image_url": image_url or "",
                    "comments": comments,
                    "likes": likes,
                    "date": post_date,
                    "url": full_url,
                }
            )

            time.sleep(random.uniform(DELAY_BETWEEN_POSTS, DELAY_BETWEEN_POSTS + 5))
        except Exception as e:
            log.error(f"Post error {href}: {e}")

    return posts


def _extract_comments(page) -> list[dict]:
    SKIP = {
        "Reels", "Mensagens", "Pesquisa", "Explorar", "Notificações", "Criar",
        "Painel", "Perfil", "Mais", "Página inicial", "Também da Meta",
        "Ver tradução", "Responder", "Editado", "Curtir", "Meta", "Sobre",
        "Blog", "Carreiras", "Ajuda", "Privacidade", "Termos", "Localizações",
        "Instagram Lite", "Meta AI", "Threads", "Meta Verified",
        "Upload de contatos e não usuários",
        "Search", "Explore", "Notifications", "Create", "Profile", "More",
        "Home", "Messages", "Reply", "Like", "Edited", "See translation",
        "Also from Meta", "Privacy", "Terms", "Locations", "Careers", "Help",
    }

    spans = page.query_selector_all("span[dir='auto']")
    texts = []
    for span in spans:
        txt = span.inner_text().strip()
        if not txt or len(txt) < 2:
            continue
        if txt in SKIP:
            continue
        if txt.startswith("Ver todas") or txt.startswith("©") or txt.startswith("View all"):
            continue
        if txt.endswith("curtidas") or txt.endswith("curtida") or txt.endswith("likes") or txt.endswith("like"):
            continue
        if re.match(r"^(há|Editado|Português)", txt):
            continue
        texts.append(txt)

    comments = []
    i = 0
    caption_skipped = False
    while i < len(texts) - 2:
        txt = texts[i]

        if not caption_skipped and ("\n" in txt or len(txt) > 100):
            caption_skipped = True
            i += 1
            continue

        next_txt = texts[i + 1] if i + 1 < len(texts) else ""
        comment_txt = texts[i + 2] if i + 2 < len(texts) else ""

        if (
            txt == next_txt
            and len(txt) < 40
            and " " not in txt.replace("_", "").replace(".", "")
            and comment_txt
            and comment_txt != txt
            and len(comment_txt) > 2
        ):
            if not re.match(r"^[\W\s]+$", comment_txt):
                comments.append(
                    {
                        "username": txt,
                        "text": comment_txt[:500],
                        "likes": 0,
                    }
                )
            i += 3
            if len(comments) >= 20:
                break
        else:
            i += 1

    return comments


def _extract_date(page) -> str | None:
    time_el = page.query_selector("time")
    if time_el:
        return time_el.get_attribute("datetime")
    return None


def _extract_likes(page) -> int:
    article = page.query_selector("article, main")
    if not article:
        return 0
    text = article.inner_text()
    m = re.search(r"([\d.,]+)\s*curtidas", text)
    if m:
        return int(m.group(1).replace(".", "").replace(",", ""))
    m = re.search(r"([\d.,]+)\s*likes", text)
    if m:
        return int(m.group(1).replace(",", "").replace(".", ""))
    return 0


def _save_posts(db: Session, username: str, posts: list[dict]) -> int:
    saved = 0
    for post in posts:
        url = post.get("url", "")
        existing = db.execute(
            select(ScrapedPost).where(
                ScrapedPost.source == username,
                ScrapedPost.url == url,
            )
        ).scalar_one_or_none()

        if not existing:
            keywords = _extract_keywords(post["caption"])

            body_parts = [post["caption"]]
            if post["comments"]:
                body_parts.append("\n---COMMENTS---")
                for c in post["comments"][:10]:
                    body_parts.append(
                        f"@{c['username']}: {c['text']} ({c['likes']} likes)"
                    )

            db.add(
                ScrapedPost(
                    source=username,
                    title=post["caption"][:500],
                    body="\n".join(body_parts),
                    url=url,
                    image_url=post.get("image_url", ""),
                    score=post.get("likes", 0),
                    comments=len(post.get("comments", [])),
                    keywords=json.dumps(keywords, ensure_ascii=False),
                )
            )
            saved += 1

    return saved


def _extract_keywords(text: str, custom_keywords: list[str] | None = None) -> list[str]:
    hashtags = re.findall(r"#(\w+)", text.lower())
    found = []
    if custom_keywords:
        found = [kw for kw in custom_keywords if kw in text.lower()]
    return list(set(hashtags + found))[:20]


if __name__ == "__main__":
    from database import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        count = scrape_instagram(db)
    finally:
        db.close()
