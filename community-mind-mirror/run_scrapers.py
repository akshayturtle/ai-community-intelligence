"""Test script: run Reddit scraper for 1 subreddit and HN scraper for 10 stories."""

import asyncio
import time

import structlog
from sqlalchemy import select, func

from database.connection import async_session, User, Post, engine, Base
from init_db import init_db
from scrapers.reddit_scraper import RedditScraper
from scrapers.hn_scraper import HNScraper

structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(0),
)

log = structlog.get_logger()


async def print_summary():
    """Print database counts."""
    async with async_session() as session:
        user_count = (await session.execute(select(func.count(User.id)))).scalar()
        post_count = (await session.execute(select(func.count(Post.id)))).scalar()

        reddit_users = (
            await session.execute(
                select(func.count(User.id)).where(User.platform_id == 1)
            )
        ).scalar()
        reddit_posts = (
            await session.execute(
                select(func.count(Post.id)).where(Post.platform_id == 1)
            )
        ).scalar()
        hn_users = (
            await session.execute(
                select(func.count(User.id)).where(User.platform_id == 2)
            )
        ).scalar()
        hn_posts = (
            await session.execute(
                select(func.count(Post.id)).where(Post.platform_id == 2)
            )
        ).scalar()

    print("\n" + "=" * 60)
    print("SCRAPER RUN SUMMARY")
    print("=" * 60)
    print(f"Total users:  {user_count}")
    print(f"Total posts:  {post_count}")
    print(f"  Reddit:     {reddit_users} users, {reddit_posts} posts")
    print(f"  HN:         {hn_users} users, {hn_posts} posts")
    print("=" * 60)


async def main():
    # Initialize database
    await init_db()

    start = time.time()

    # Run Reddit scraper for 1 subreddit
    print("\n--- Running Reddit scraper (r/artificial) ---")
    reddit = RedditScraper()
    await reddit.run(subreddits=["artificial"])

    # Run HN scraper for 10 stories
    print("\n--- Running HN scraper (10 stories) ---")
    hn = HNScraper()
    await hn.run(max_stories=10, story_types=["topstories"])

    elapsed = time.time() - start

    await print_summary()
    print(f"\nTime taken: {elapsed:.1f}s")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
