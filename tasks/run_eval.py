import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.services.eval_service import run_eval


async def main() -> None:
    eval_key = sys.argv[1] if len(sys.argv) > 1 else "custom_eval"
    db = SessionLocal()
    try:
        results = await run_eval(db, eval_key, ["deepseek", "dashscope", "qianfan"])
        print(results)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
