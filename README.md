# llm-watch

`llm-watch` 是一个轻量 Web 平台，用于横向监测 DeepSeek、DashScope、Qianfan 三家大模型 API 的可用性、性能、缓存表现和评测结果。

## 功能概览

- FastAPI 后端
- SQLite + SQLAlchemy 持久化
- APScheduler 自动健康探测
- Jinja2 + ECharts 看板
- 统一 adapter 模式封装 provider 差异
- OpenClaw 本地 skill
- Docker / Docker Compose 部署

## 目录结构

```text
llm-watch/
├─ app/
├─ data/
├─ datasets/
├─ tasks/
├─ scripts/
├─ skills/
├─ requirements.txt
├─ Dockerfile
├─ docker-compose.yml
└─ .env.example
```

## 启动步骤

### 1. 复制环境变量

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

### 2. 安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. 初始化数据库

```bash
python scripts/init_db.py
python scripts/seed_providers.py
```

### 4. 启动服务

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问页面

- Dashboard: `http://127.0.0.1:8000/`
- Compare: `http://127.0.0.1:8000/compare`
- Evals: `http://127.0.0.1:8000/evals`
- API Docs: `http://127.0.0.1:8000/docs`

## Docker 部署

```bash
cp .env.example .env
docker compose up --build
```

## API 列表

- `GET /api/health`
- `GET /api/providers`
- `POST /api/providers/test`
- `POST /api/chat`
- `POST /api/probes/health/run`
- `POST /api/probes/perf/run`
- `POST /api/probes/cache/run`
- `GET /api/probes/runs`
- `POST /api/evals/run`
- `GET /api/evals/results`
- `GET /api/dashboard/summary`
- `GET /api/dashboard/compare`

## 数据说明

- `datasets/benchmark_small.jsonl`
- `datasets/custom_eval.jsonl`

评分方式支持：

- `contains`
- `exact`
- `regex`
- `json_schema`

## 常用脚本

- `python tasks/run_health_probe.py`
- `python tasks/run_perf_probe.py`
- `python tasks/run_cache_probe.py`
- `python tasks/run_eval.py custom_eval`

## OpenClaw Skill

本地 skill 位于 `skills/llm-watch/SKILL.md`。

## 注意事项

- 如果 provider 没有返回缓存字段，平台会将 `cached_tokens` 记为 `0`
- 所有异常会返回统一 JSON 错误结构
- 首版默认只自动执行 `health probe`
