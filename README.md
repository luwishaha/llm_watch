# llm-watch

`llm-watch` 是一个基于 FastAPI + Jinja2 + SQLite 的轻量 LLM API 监控面板，用来观察多 provider / model 的可用性、延迟、吞吐、缓存表现和评测结果。

## 本轮增强

- 首页升级为 8 个指标卡片：
  - `availability_24h`
  - `avg_ttft_24h`
  - `avg_tps_24h`
  - `latest_custom_eval`
  - `p95_ttft_24h`
  - `p95_latency_24h`
  - `avg_tpot_24h`
  - `goodput_24h`
- 首页新增 `Benchmark Summary` 摘要区块：
  - 最近一次 benchmark 运行时间
  - 每个 provider/model 的最近 benchmark 综合分
  - best / worst benchmark model
  - 横向柱状图
- 新增 eval set 导入能力：
  - `GET /api/eval-sets`
  - `POST /api/eval-sets/import-text`
  - `POST /api/eval-sets/upload`
- OpenClaw skill 新增 eval set 列表、文本导入、文件上传、导入后立即运行示例

## 指标说明

- `p95_ttft_24h`
  - 最近 24 小时内 `run_type=perf` 的 `ttft_ms` 的 p95。
- `p95_latency_24h`
  - 最近 24 小时内 `run_type=perf` 的 `latency_ms` 的 p95。
- `avg_tpot_24h`
  - 对每条 `perf` 记录计算：
    - `(latency_ms - ttft_ms) / max(completion_tokens - 1, 1)`
  - `ttft_ms` 为空时跳过。
  - 单位为 `ms/token`。
- `goodput_24h`
  - 最近 24 小时满足以下条件的 `perf` 请求占比：
    - `success = true`
    - `ttft_ms <= 1500`
    - `latency_ms <= 8000`
    - 输出非空
    - `completion_tokens > 0`

## 目录结构

```text
llm-watch/
├─ app/
├─ data/
├─ datasets/
│  ├─ benchmark_small.jsonl
│  ├─ custom_eval.jsonl
│  └─ uploaded/
├─ scripts/
├─ skills/
├─ tasks/
├─ tests/
├─ requirements.txt
├─ Dockerfile
├─ docker-compose.yml
└─ .env.example
```

## 快速启动

### 1. 配置环境变量

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
- OpenAPI Docs: `http://127.0.0.1:8000/docs`

## Dashboard 与 Compare API

- `GET /api/dashboard/summary`
  - 返回首页 8 个指标卡片数据和 `latest_benchmark_summary`。
- `GET /api/dashboard/compare`
  - 返回 compare 表格数据。
  - 当前 compare item 包含：
    - `availability`
    - `avg_latency_ms`
    - `avg_ttft_ms`
    - `p95_ttft_ms`
    - `p95_latency_ms`
    - `avg_tps`
    - `avg_tpot_ms`
    - `goodput`
    - `avg_cached_tokens`
    - `latest_eval_score`

## Eval Set 导入

### 1. 查看全部 eval sets

```bash
curl -s http://127.0.0.1:8000/api/eval-sets
```

### 2. 通过粘贴 JSONL 文本导入

```bash
curl -s -X POST http://127.0.0.1:8000/api/eval-sets/import-text \
  -H "Content-Type: application/json" \
  -d '{
    "eval_key":"demo_set",
    "eval_name":"Demo Set",
    "source_type":"custom",
    "content":"{\"id\":\"1\",\"prompt\":\"hi\",\"expected\":\"hello\",\"scoring\":\"contains\"}",
    "enabled":true
  }'
```

### 3. 通过本地 `.jsonl` 文件上传导入

```bash
curl -s -F "file=@datasets/custom_eval.jsonl" \
  -F "eval_key=upload_demo" \
  -F "eval_name=Upload Demo" \
  -F "source_type=custom" \
  -F "enabled=true" \
  http://127.0.0.1:8000/api/eval-sets/upload
```

### 4. 导入后立即运行 eval

```bash
curl -s -X POST http://127.0.0.1:8000/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"eval_set":"upload_demo","providers":["deepseek","dashscope","qianfan"]}'
```

导入文件会保存到：

```text
datasets/uploaded/{eval_key}.jsonl
```

重复 `eval_key` 时会覆盖更新 `eval_sets` 记录与上传文件。

## 其它常用 API

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

## OpenClaw Skill

仓库内置了 `skills/llm-watch/SKILL.md`，支持：

- summary 查询
- compare 查询
- probe 触发
- eval 触发
- eval set 列表查询
- 文本导入 eval set
- 文件上传导入 eval set
- 导入后直接运行 eval

## PowerShell 示例

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/api/eval-sets"

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/probes/perf/run" `
  -ContentType "application/json" `
  -Body '{"providers":[],"prompt_template":"standard_short","max_tokens":128}'

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/evals/run" `
  -ContentType "application/json" `
  -Body '{"eval_set":"custom_eval","providers":[]}'
```

## 注意事项

- `.env` 使用项目绝对路径加载，不依赖当前启动目录。
- 所有新增导入异常继续走统一 JSON 错误结构。
- 首页 `Benchmark Summary` 只展示摘要，不展示 case 详情。
- benchmark 数据为空时，首页和接口都会优雅返回空结构，不报错。
