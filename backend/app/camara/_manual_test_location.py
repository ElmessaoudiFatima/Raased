# backend/app/camara/_manual_test_location.py
import asyncio
from app.camara.location import fetch_location

NUMBERS = [
    "+99999991000",
    "+99999991001",
    "+99999990400",
    "+99999990404",
    "+99999990422",
    "+99999990500",
    "+99999990502",
    "+99999990503",
    "+99999990504",
    "+36719991000",
]


async def main():
    for number in NUMBERS:
        try:
            result = await fetch_location(number, max_age=60)
            print(f"{number}: {result}")
        except Exception as e:
            print(f"{number}: ERROR - {e}")
        await asyncio.sleep(0.3)


if __name__ == "__main__":
    asyncio.run(main())