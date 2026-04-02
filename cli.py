import argparse
import sys

from sqlalchemy import select

from database import SessionLocal, init_db
from models import ScrapingProfile


def add_profile(username: str, display_name: str, category: str = "general", priority: int = 5):
    db = SessionLocal()
    existing = db.execute(
        select(ScrapingProfile).where(ScrapingProfile.username == username)
    ).scalar_one_or_none()

    if existing:
        print(f"Profile @{username} already exists.")
        db.close()
        return

    db.add(ScrapingProfile(
        username=username,
        display_name=display_name,
        category=category,
        priority=priority,
    ))
    db.commit()
    db.close()
    print(f"Added @{username} ({display_name}) [category={category}, priority={priority}]")


def remove_profile(username: str):
    db = SessionLocal()
    profile = db.execute(
        select(ScrapingProfile).where(ScrapingProfile.username == username)
    ).scalar_one_or_none()

    if not profile:
        print(f"Profile @{username} not found.")
        db.close()
        return

    db.delete(profile)
    db.commit()
    db.close()
    print(f"Removed @{username}")


def list_profiles():
    db = SessionLocal()
    profiles = db.execute(
        select(ScrapingProfile).order_by(ScrapingProfile.priority.desc())
    ).scalars().all()

    if not profiles:
        print("No profiles configured. Use `python cli.py add <username> <name>` to add one.")
        db.close()
        return

    print(f"{'Username':<25} {'Name':<25} {'Category':<12} {'Priority':<8} {'Active':<7} {'Posts':<6} {'Last Scraped'}")
    print("-" * 110)
    for p in profiles:
        last = p.last_scraped_at.strftime("%Y-%m-%d %H:%M") if p.last_scraped_at else "never"
        active = "yes" if p.is_active else "no"
        print(f"@{p.username:<24} {p.display_name:<25} {p.category:<12} {p.priority:<8} {active:<7} {p.post_count:<6} {last}")

    db.close()


def toggle_profile(username: str):
    db = SessionLocal()
    profile = db.execute(
        select(ScrapingProfile).where(ScrapingProfile.username == username)
    ).scalar_one_or_none()

    if not profile:
        print(f"Profile @{username} not found.")
        db.close()
        return

    profile.is_active = not profile.is_active
    db.commit()
    state = "active" if profile.is_active else "inactive"
    db.close()
    print(f"@{username} is now {state}")


def main():
    parser = argparse.ArgumentParser(description="Manage Instagram scraping profiles")
    sub = parser.add_subparsers(dest="command")

    add_parser = sub.add_parser("add", help="Add a profile to scrape")
    add_parser.add_argument("username", help="Instagram username (without @)")
    add_parser.add_argument("display_name", help="Display name")
    add_parser.add_argument("--category", default="general", help="Category (default: general)")
    add_parser.add_argument("--priority", type=int, default=5, help="Priority 1-10 (default: 5)")

    rm_parser = sub.add_parser("remove", help="Remove a profile")
    rm_parser.add_argument("username", help="Instagram username")

    sub.add_parser("list", help="List all profiles")

    toggle_parser = sub.add_parser("toggle", help="Toggle profile active/inactive")
    toggle_parser.add_argument("username", help="Instagram username")

    sub.add_parser("run", help="Run the scraper now")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    init_db()

    if args.command == "add":
        add_profile(args.username, args.display_name, args.category, args.priority)
    elif args.command == "remove":
        remove_profile(args.username)
    elif args.command == "list":
        list_profiles()
    elif args.command == "toggle":
        toggle_profile(args.username)
    elif args.command == "run":
        from scraper import scrape_instagram
        db = SessionLocal()
        try:
            count = scrape_instagram(db)
            print(f"\nTotal new posts: {count}")
        finally:
            db.close()


if __name__ == "__main__":
    main()
