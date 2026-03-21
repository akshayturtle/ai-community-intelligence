"""Initialize database: create all tables and seed platforms."""

import asyncio

from sqlalchemy import select

from database.connection import Base, engine, async_session, Platform


SEED_PLATFORMS = [
    "reddit",
    "hackernews",
    "youtube",
    "twitter",
    "linkedin",
    "producthunt",
    "stackoverflow",
    "discord",
    "mastodon",
    "bluesky",
]


async def init_db():
    print("Creating all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

    print("Seeding platforms...")
    async with async_session() as session:
        result = await session.execute(select(Platform))
        existing = {p.name for p in result.scalars().all()}

        added = 0
        for name in SEED_PLATFORMS:
            if name not in existing:
                session.add(Platform(name=name))
                added += 1

        await session.commit()
        print(f"Platforms seeded: {added} new, {len(existing)} already existed.")

    print("Database initialization complete.")


if __name__ == "__main__":
    asyncio.run(init_db())
