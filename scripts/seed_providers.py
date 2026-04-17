from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text

from app.db import engine


SEED_SQL = """
INSERT OR IGNORE INTO providers (provider_key, provider_name, base_url, api_key_env)
VALUES
('deepseek', 'DeepSeek', 'https://api.deepseek.com', 'DEEPSEEK_API_KEY'),
('dashscope', '阿里百炼', 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'DASHSCOPE_API_KEY'),
('qianfan', '百度千帆', 'https://qianfan.baidubce.com/v2', 'QIANFAN_API_KEY');

INSERT OR IGNORE INTO models (provider_id, model_key, model_name)
SELECT id, 'deepseek-chat', 'deepseek-chat' FROM providers WHERE provider_key='deepseek';

INSERT OR IGNORE INTO models (provider_id, model_key, model_name)
SELECT id, 'qwen-plus', 'qwen-plus' FROM providers WHERE provider_key='dashscope';

INSERT OR IGNORE INTO models (provider_id, model_key, model_name)
SELECT id, 'ernie-4.0-turbo-128k', 'ernie-4.0-turbo-128k' FROM providers WHERE provider_key='qianfan';

INSERT OR IGNORE INTO eval_sets (eval_key, eval_name, source_type, dataset_path)
VALUES
('benchmark_small', 'Benchmark Small', 'public', 'datasets/benchmark_small.jsonl'),
('custom_eval', 'Custom Eval', 'custom', 'datasets/custom_eval.jsonl');
"""


def main() -> None:
    statements = [stmt.strip() for stmt in SEED_SQL.split(";") if stmt.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
    print("Seed data inserted.")


if __name__ == "__main__":
    main()
