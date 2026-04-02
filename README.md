# Instagram Scraper

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-2DA44E?logo=playwright&logoColor=white)](https://playwright.dev)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)](https://sqlite.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub](https://img.shields.io/badge/@HugoluizMTB-181717?logo=github&logoColor=white)](https://github.com/HugoluizMTB)

A Python-based Instagram scraper using Playwright with session-based authentication. Scrapes posts, captions, comments, and likes from public profiles — no API keys needed.

Built with safety-first design: rate limiting, session management, and anti-detection measures to minimize the risk of account restrictions.

> **WARNING: NEVER use your personal Instagram account for scraping.**
> Create a dedicated secondary account. Instagram may restrict or ban accounts that show automated behavior. You have been warned.

## Features

- **Session-based auth** — Login once via browser, session stored securely in `.env` (base64)
- **Persistent browser profile** — Login is remembered between runs, renew every ~90 days
- **Post scraping** — Captions, images, likes, comments with usernames
- **Comment extraction** — Parses Instagram's DOM structure to extract real comments
- **Date filtering** — Only scrapes posts from the last N days (configurable)
- **Anti-detection** — Randomized delays, session time limits, safe hours, human-like behavior
- **Rate limiting** — Configurable delays between profiles and posts
- **Keyword extraction** — Extracts hashtags and custom keywords from captions
- **SQLite storage** — Saves everything to a local database with deduplication
- **Profile management** — CLI to add/remove/toggle profiles and set priorities
- **Docker ready** — Dockerfile + docker-compose for deployment on any VPS

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your **secondary account** credentials:

```env
INSTAGRAM_USERNAME=your_secondary_account
INSTAGRAM_PASSWORD=your_password
```

### 3. Login and save session

```bash
python login.py
```

This opens a real Chrome browser with a persistent profile. Log into Instagram manually in the browser window (Instagram blocks automated login on fresh browsers). Once you see your feed, go back to the terminal and press ENTER — the session cookies are saved to `.env` as `INSTAGRAM_COOKIES`.

The browser profile is saved locally, so next time you run `login.py` you'll already be logged in. Session lasts ~90 days — run `login.py` again to renew.

### 4. Add profiles to scrape

```bash
python cli.py add natgeo "National Geographic" --category media
python cli.py add nasa "NASA" --category science
python cli.py add nike "Nike" --category brand --priority 8
python cli.py list
```

### 5. Run the scraper

```bash
python scraper.py
```

## CLI Reference

```bash
python cli.py add <username> "<display_name>" [--category general] [--priority 5]
python cli.py remove <username>
python cli.py list
python cli.py toggle <username>   # activate/deactivate
python cli.py run                 # run scraper
```

## Project Structure

```
instagram-scraper/
├── scraper.py          # Main scraper logic
├── models.py           # SQLAlchemy models (profiles + posts)
├── database.py         # Database setup
├── config.py           # Configuration (from .env)
├── cli.py              # CLI for managing profiles
├── login.py            # Login helper (saves session to .env)
├── Dockerfile          # Container with Playwright + Chromium
├── docker-compose.yml  # One-command deployment
├── .env.example        # Environment variables template
├── .gitignore
├── requirements.txt
└── README.md
```

## Where is data stored?

| Data | Location | Security |
|------|----------|----------|
| Credentials | `.env` (gitignored) | Never committed to repo |
| Session cookies | `.env` as `INSTAGRAM_COOKIES` (base64) | Never committed to repo |
| Scraped posts | `data/scraper.db` (SQLite, gitignored) | Local only |
| In Docker | `scraper_data` volume | Persists across container restarts |

Nothing sensitive ever touches the repository.

## Docker Deployment

### Build and run locally

```bash
docker compose build
docker compose up
```

### Deploy to a VPS

1. **On your local machine** — run `python login.py` to authenticate
2. **Copy `.env`** to the server (scp, rsync, or paste into your hosting platform)
3. **On the server:**
   ```bash
   docker compose up -d
   ```

The session cookies are in `.env`, so the container runs headless without needing a browser login on the server.

### Run on a schedule

Uncomment the schedule line in `docker-compose.yml`, or use cron:

```bash
# Run twice a day at 10:00 and 18:00
0 10,18 * * * cd /path/to/instagram-scraper && docker compose run --rm scraper
```

### Session renewal (~every 90 days)

1. On your local machine: `python login.py`
2. Copy the updated `INSTAGRAM_COOKIES` value from `.env` to the server
3. Restart the container: `docker compose restart`

## Anti-Block Safety Guide

Instagram actively detects and blocks automated behavior. This scraper includes several safety mechanisms:

### Built-in protections

| Protection | Default | Why |
|-----------|---------|-----|
| Randomized delays | 30-60s between profiles | Mimics human browsing speed |
| Post delay | 8-13s between posts | Avoids rapid-fire requests |
| Session time limit | 20 min max | Long sessions trigger flags |
| Safe hours only | 7:00-23:00 | Nighttime activity is suspicious |
| Max profiles/run | 15 | Keeps volume low per session |
| Max posts/profile | 6 | Only recent posts, less load |
| Cookie refresh | Every run | Keeps session alive |
| Anti-webdriver | Always on | Hides Playwright detection |
| Human-like UA | Chrome on macOS | Matches real browser fingerprint |

### Recommended practices

1. **Use a secondary account** — Never scrape with your main account
2. **Start slow** — Begin with 3-5 profiles, increase gradually over days
3. **Don't run too often** — 2x/day max is safe, 1x/day is safer
4. **Vary your schedule** — Don't run at the exact same time every day
5. **Monitor for warnings** — If you see login challenges or CAPTCHAs, stop for 24-48h
6. **Keep volumes low** — Under 100 profiles/day total is a safe ceiling
7. **Use residential IPs** — Datacenter IPs get flagged faster (relevant for VPS)

### Signs you're being rate-limited

- Login page shown instead of profile (cookies expired or flagged)
- "Page not available" on profiles that exist
- CAPTCHAs or "suspicious activity" prompts
- Slower page loads or empty responses

**If any of these happen:** stop immediately, wait 24-48h, run `login.py` again, and reduce your limits in `.env`.

## Use Cases

### Brand monitoring
Track competitor posts and engagement:
```bash
python cli.py add nike "Nike" --category brand --priority 8
python cli.py add adidas "Adidas" --category brand --priority 8
python cli.py add puma "PUMA" --category brand --priority 7
```

### Research / Academic
Collect public posts for content analysis:
```env
# In .env — increase history depth
MAX_DAYS=30
MAX_POSTS_PER_PROFILE=12
```

### Content aggregation
Monitor creators in your niche:
```bash
python cli.py add creator1 "Creator One" --category creator
python cli.py add creator2 "Creator Two" --category creator
```

### Export to CSV
```python
import csv
from database import get_db
from models import ScrapedPost

db = next(get_db())
posts = db.query(ScrapedPost).all()
with open("export.csv", "w") as f:
    writer = csv.writer(f)
    writer.writerow(["source", "caption", "likes", "comments", "date", "url"])
    for p in posts:
        writer.writerow([p.source, p.title, p.score, p.comments, p.created_at, p.url])
```

## Configuration Reference

All settings in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `INSTAGRAM_USERNAME` | — | Secondary account username |
| `INSTAGRAM_PASSWORD` | — | Secondary account password |
| `INSTAGRAM_COOKIES` | — | Auto-filled by `login.py` |
| `DATABASE_URL` | `sqlite:///./data/scraper.db` | Database connection string |
| `MAX_PROFILES_PER_RUN` | `15` | Max profiles per scraping session |
| `MIN_DELAY_SECONDS` | `30` | Min delay between profiles |
| `MAX_DELAY_SECONDS` | `60` | Max delay between profiles |
| `MAX_SESSION_MINUTES` | `20` | Max session duration |
| `DELAY_BETWEEN_POSTS` | `8` | Min delay between posts |
| `MAX_DAYS` | `5` | Only scrape posts from last N days |
| `MAX_POSTS_PER_PROFILE` | `6` | Max posts to scrape per profile |
| `SAFE_HOUR_START` | `7` | Start of safe scraping window |
| `SAFE_HOUR_END` | `23` | End of safe scraping window |

## Important Notes

- This tool scrapes **public profiles only** using a logged-in session for access
- Instagram's Terms of Service restrict automated data collection — use responsibly
- This is intended for **personal use, research, and education**
- The author is not responsible for any account restrictions resulting from use
- Always respect people's privacy and applicable data protection laws (GDPR, LGPD, etc.)

## Author

**Hugo Luiz** — [@HugoluizMTB](https://github.com/HugoluizMTB)

## License

MIT
