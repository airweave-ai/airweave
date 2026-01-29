import asyncio
from sqlalchemy import select
from airweave.db.session import SessionLocal
from airweave.models.source import Source


async def check():
    async with SessionLocal() as db:
        result = await db.execute(select(Source).where(Source.short_name == "sharepoint2019v2"))
        source = result.scalar_one_or_none()

        if source:
            print(f"✓ SharePoint 2019 V2 source exists")
            print(f"  short_name: {source.short_name}")
            print(f"  feature_flag: {source.feature_flag}")
        else:
            print("✗ SharePoint 2019 V2 source NOT found in database")
            print("  The source needs to be synced to the database first")


asyncio.run(check())
