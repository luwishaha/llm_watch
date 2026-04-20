---
name: llm_watch
description: Use when the user wants to query or operate the local LLM API monitoring dashboard, including dashboard summary, provider comparison, probe reruns, eval reruns, eval-set listing, and eval-set import through the local service API.
user-invocable: true
metadata: {"openclaw":{"os":["win32","linux"],"requires":{"bins":["curl"]}}}
---

# LLM Watch Skill

Use this skill when the user wants to work with the local `llm-watch` service running at:

- `http://127.0.0.1:8000`

## Supported requests

This skill supports the following user intents:

- view the latest dashboard summary
- compare enabled providers and models
- inspect recent probe runs
- rerun `health`, `perf`, or `cache` probes
- rerun `custom_eval` or `benchmark_small`
- inspect recent eval results
- list available eval sets
- import a new eval set from pasted JSONL text
- upload a local `.jsonl` eval set file
- import an eval set and run it immediately

## Rules

1. Prefer the local monitoring API over calling upstream provider APIs directly.
2. Use `GET` endpoints for read-only questions.
3. Use `POST` endpoints for actions such as probe reruns, eval reruns, and eval-set imports.
4. Keep answers concise:
   - short summary first
   - then key metrics or returned items
   - then notable anomalies or failures
5. If a request fails, report the HTTP status and a brief response-body summary.
6. Never expose API keys or raw environment-variable contents.

## Command style

On both Windows and Linux, `curl` examples are valid.

On Windows PowerShell, prefer `curl.exe` instead of the `curl` alias if shell behavior is inconsistent.

## Read commands

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

### 4) Read recent eval results

```bash
curl -s "http://127.0.0.1:8000/api/evals/results?eval_set=custom_eval&limit=10"
```

### 5) List eval sets

```bash
curl -s http://127.0.0.1:8000/api/eval-sets
```

## Probe commands

### 6) Trigger health probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/health/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"]}'
```

### 7) Trigger perf probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/perf/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"],"prompt_template":"standard_short","max_tokens":128}'
```

### 8) Trigger cache probe

```bash
curl -s -X POST http://127.0.0.1:8000/api/probes/cache/run \
  -H "Content-Type: application/json" \
  -d '{"providers":["deepseek","dashscope","qianfan"],"prompt_template":"long_prefix_cache"}'
```

## Eval commands

### 9) Trigger `custom_eval`

```bash
curl -s -X POST http://127.0.0.1:8000/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"eval_set":"custom_eval","providers":["deepseek","dashscope","qianfan"]}'
```

### 10) Trigger `benchmark_small`

```bash
curl -s -X POST http://127.0.0.1:8000/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"eval_set":"benchmark_small","providers":["deepseek","dashscope","qianfan"]}'
```

## Eval-set import commands

### 11) Import eval set from pasted JSONL text

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

### 12) Upload eval set from local `.jsonl` file

```bash
curl -s -F "file=@datasets/custom_eval.jsonl" \
  -F "eval_key=upload_demo" \
  -F "eval_name=Upload Demo" \
  -F "source_type=custom" \
  -F "enabled=true" \
  http://127.0.0.1:8000/api/eval-sets/upload
```

### 13) Import then run

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

```bash
curl -s -X POST http://127.0.0.1:8000/api/evals/run \
  -H "Content-Type: application/json" \
  -d '{"eval_set":"demo_set","providers":["deepseek","dashscope","qianfan"]}'
```

## PowerShell examples

### Read dashboard summary

```powershell
curl.exe -s http://127.0.0.1:8000/api/dashboard/summary
```

### Trigger perf probe

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/probes/perf/run `
  -H "Content-Type: application/json" `
  -d "{\"providers\":[\"deepseek\",\"dashscope\",\"qianfan\"],\"prompt_template\":\"standard_short\",\"max_tokens\":128}"
```

### Trigger `custom_eval`

```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/evals/run `
  -H "Content-Type: application/json" `
  -d "{\"eval_set\":\"custom_eval\",\"providers\":[\"deepseek\",\"dashscope\",\"qianfan\"]}"
```
