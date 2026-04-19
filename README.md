# llm-watch

`llm-watch` 是一个轻量 Web 平台，用于横向监测多个大模型 API 的可用性、性能、缓存表现和评测结果。

## 功能概览

- FastAPI 后端
- SQLite + SQLAlchemy 持久化
- APScheduler 自动健康探测
- Jinja2 + ECharts 看板
- 统一 adapter 模式封装 provider 差异
- OpenClaw 本地 skill
- Docker / Docker Compose 部署
- `.env` 动态驱动 provider 列表、模型名和 base_url

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

## provider 配置方式

内置 provider 仍然支持：

- `DEEPSEEK_*`
- `DASHSCOPE_*`
- `QIANFAN_*`

如果你想新增 provider，可以直接在 `.env` 中增加：

- `LLM_WATCH_PROVIDERS=deepseek,dashscope,qianfan,openrouter`
- `OPENROUTER_API_KEY=...`
- `OPENROUTER_BASE_URL=...`
- `OPENROUTER_MODEL=...`
- `OPENROUTER_NAME=OpenRouter`
- `OPENROUTER_ENABLED=true`

只要是 OpenAI-compatible 的 `/chat/completions` 接口，就可以直接接进来。

## 注意事项

- `.env` 使用项目绝对路径加载，不依赖当前启动目录
- `.env` 中的 provider、model、base_url 变更会在接口请求时动态同步到数据库和前端展示
- 如果 provider 没有返回缓存字段，平台会将 `cached_tokens` 记为 `0`
- 所有异常会返回统一 JSON 错误结构
- 首版默认只自动执行 `health probe`
