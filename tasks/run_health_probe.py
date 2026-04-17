import asyncio
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.services.probe_service import run_health_probe


async def main() -> None:
    db = SessionLocal()
    try:
        results = await run_health_probe(db, ["deepseek", "dashscope", "qianfan"])
        print(results)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
