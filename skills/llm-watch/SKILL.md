---
name: llm_watch
description: Query and operate the local LLM API monitoring dashboard, including provider comparison, probe runs, eval runs, and summary reporting.
metadata:
  openclaw:
    os: ["linux"]
    requires:
      bins: ["curl"]
---

# LLM Watch Skill

Use this skill when the user wants to:

- compare model API availability, TTFT, generation speed, or cache behavior
- inspect the latest monitoring summary
- rerun health/performance/cache probes
- rerun benchmark or custom evaluation
- check which provider/model performed best or worst recently

This skill assumes a local monitoring service is running at:

- `http://127.0.0.1:8000`

## Rules

1. Prefer using the local monitoring API instead of calling provider APIs directly.
2. For read-only questions, call GET endpoints first.
3. For active operations such as rerunning probes or evals, call POST endpoints.
4. Keep responses concise and structured:
   - short summary first
   - then key metrics
   - then notable anomalies
5. If an endpoint fails, report the HTTP status and response body briefly.
6. Never expose API keys or environment variable contents.

## Common operations

### 1) Get dashboard summary

```bash
curl -s http://127.0.0.1:8000/api/dashboard/summary
```

### 2) Compare providers

```bash
curl -s "http://127.0.0.1:8000/api/dashboard/compare?providers=deepseek,dashscope,qianfan&window=24h"
```

### 3) List recent probe runs

```bash
curl -s "http://127.0.0.1:8000/api/probes/runs?limit=20"
```

### 4) Trigger health probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/health/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"]}'
```

### 5) Trigger perf probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/perf/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"],"prompt_template":"standard_short","max_tokens":128}'
```

### 6) Trigger cache probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/cache/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"],"prompt_template":"long_prefix_cache"}'
```

### 7) Trigger evaluation

```bash
curl -s -X POST http://127.0.0.1:8000/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"eval_set":"custom_eval","providers":["deepseek","dashscope","qianfan"]}'
```

### 8) Read latest evaluation results

```bash
curl -s "http://127.0.0.1:8000/api/evals/results?eval_set=custom_eval&limit=10"
```
