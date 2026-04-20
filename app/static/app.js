async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || `Request failed: ${response.status}`);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toFixed(digits).replace(/\.00$/, "");
}

function formatMetric(value, suffix = "", digits = 2) {
  const formatted = formatNumber(value, digits);
  return formatted === "-" ? formatted : `${formatted}${suffix}`;
}

function formatPercent(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "-";
  }
  return `${(Number(value) * 100).toFixed(digits).replace(/\.0+$/, "")}%`;
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function setText(id, text) {
  const element = document.getElementById(id);
  if (element) {
    element.textContent = text;
  }
}

function initBarChart(elementId, labels, values, name, color, config = {}) {
  const target = document.getElementById(elementId);
  if (!target || typeof echarts === "undefined") {
    return;
  }
  const chart = echarts.init(target);
  if (config.horizontal) {
    chart.setOption({
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      grid: { left: 90, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "value" },
      yAxis: { type: "category", data: labels },
      series: [{ name, type: "bar", data: values, itemStyle: { color, borderRadius: [0, 10, 10, 0] } }],
    });
    return;
  }
  chart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 20, top: 30, bottom: 50 },
    xAxis: { type: "category", data: labels, axisLabel: { interval: 0, rotate: labels.length > 4 ? 20 : 0 } },
    yAxis: { type: "value" },
    series: [{ name, type: "bar", data: values, itemStyle: { color, borderRadius: [8, 8, 0, 0] } }],
  });
}

function initGroupedBarChart(elementId, labels, seriesList, colors) {
  const target = document.getElementById(elementId);
  if (!target || typeof echarts === "undefined") {
    return;
  }
  const chart = echarts.init(target);
  chart.setOption({
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { top: 0 },
    grid: { left: 40, right: 20, top: 40, bottom: 50 },
    xAxis: { type: "category", data: labels, axisLabel: { interval: 0, rotate: labels.length > 4 ? 20 : 0 } },
    yAxis: { type: "value" },
    series: seriesList.map((series, index) => ({
      name: series.name,
      type: "bar",
      data: series.values,
      itemStyle: { color: colors[index], borderRadius: [8, 8, 0, 0] },
    })),
  });
}

function sortByValue(items, direction = "desc", field = "value") {
  return [...items].filter(item => item[field] !== null && item[field] !== undefined).sort((a, b) => {
    return direction === "desc" ? b[field] - a[field] : a[field] - b[field];
  });
}

function benchmarkModelLabel(item) {
  return `${item.provider}/${item.model}`;
}

async function loadProviders() {
  const payload = await fetchJson("/api/providers");
  return payload.items || [];
}

async function loadDashboard() {
  const payload = await fetchJson("/api/dashboard/summary");
  const summary = payload.summary || {};

  const availability = summary.availability_24h || [];
  const ttft = summary.avg_ttft_24h || [];
  const tps = summary.avg_tps_24h || [];
  const evals = summary.latest_custom_eval || [];
  const p95Ttft = summary.p95_ttft_24h || [];
  const p95Latency = summary.p95_latency_24h || [];
  const tpot = summary.avg_tpot_24h || [];
  const goodput = summary.goodput_24h || [];
  const benchmark = summary.latest_benchmark_summary || { items: [] };

  const bestAvailability = sortByValue(availability, "desc")[0];
  const bestTtft = sortByValue(ttft, "asc")[0];
  const bestTps = sortByValue(tps, "desc")[0];
  const bestEval = sortByValue(evals, "desc", "score")[0];
  const bestP95Ttft = sortByValue(p95Ttft, "asc")[0];
  const bestP95Latency = sortByValue(p95Latency, "asc")[0];
  const bestTpot = sortByValue(tpot, "asc")[0];
  const bestGoodput = sortByValue(goodput, "desc")[0];

  setText("metric-availability", bestAvailability ? `${bestAvailability.provider} ${formatPercent(bestAvailability.value)}` : "-");
  setText("metric-ttft", bestTtft ? `${bestTtft.provider} ${formatMetric(bestTtft.value, " ms")}` : "-");
  setText("metric-tps", bestTps ? `${bestTps.provider} ${formatMetric(bestTps.value)}` : "-");
  setText("metric-eval", bestEval ? `${bestEval.provider} ${formatMetric(bestEval.score, "", 4)}` : "-");
  setText("metric-p95-ttft", bestP95Ttft ? `${bestP95Ttft.provider} ${formatMetric(bestP95Ttft.value, " ms")}` : "-");
  setText("metric-p95-latency", bestP95Latency ? `${bestP95Latency.provider} ${formatMetric(bestP95Latency.value, " ms")}` : "-");
  setText("metric-tpot", bestTpot ? `${bestTpot.provider} ${formatMetric(bestTpot.value, " ms/token")}` : "-");
  setText("metric-goodput", bestGoodput ? `${bestGoodput.provider} ${formatPercent(bestGoodput.value)}` : "-");

  setText("benchmark-last-run", formatDateTime(benchmark.last_run_at));
  setText("benchmark-best", benchmark.best_model ? `${benchmark.best_model.provider}/${benchmark.best_model.model} (${formatMetric(benchmark.best_model.score, "", 4)})` : "-");
  setText("benchmark-worst", benchmark.worst_model ? `${benchmark.worst_model.provider}/${benchmark.worst_model.model} (${formatMetric(benchmark.worst_model.score, "", 4)})` : "-");

  initBarChart(
    "chart-availability",
    availability.map(item => item.provider),
    availability.map(item => item.value ?? 0),
    "Availability",
    "#cb5f35"
  );
  initBarChart(
    "chart-ttft",
    ttft.map(item => item.provider),
    ttft.map(item => item.value ?? 0),
    "TTFT",
    "#6a8491"
  );
  initBarChart(
    "chart-tps",
    tps.map(item => item.provider),
    tps.map(item => item.value ?? 0),
    "TPS",
    "#8c6f56"
  );

  const evalList = document.getElementById("latest-evals");
  if (evalList) {
    evalList.innerHTML = evals.length
      ? evals.map(item => `<li><strong>${escapeHtml(item.provider)}</strong> <span>${formatMetric(item.score, "", 4)}</span></li>`).join("")
      : `<li class="empty-state">暂无 custom eval 数据。</li>`;
  }

  const benchmarkItems = document.getElementById("benchmark-items");
  const benchmarkEmpty = document.getElementById("benchmark-empty");
  const benchmarkRows = benchmark.items || [];
  if (benchmarkItems) {
    benchmarkItems.innerHTML = benchmarkRows.map(item => `
      <li>
        <strong>${escapeHtml(benchmarkModelLabel(item))}</strong>
        <span>${formatMetric(item.score, "", 4)} · ${formatDateTime(item.run_at)}</span>
      </li>
    `).join("");
  }
  if (benchmarkEmpty) {
    benchmarkEmpty.style.display = benchmarkRows.length ? "none" : "block";
  }

  initBarChart(
    "chart-benchmark",
    benchmarkRows.map(item => benchmarkModelLabel(item)),
    benchmarkRows.map(item => item.score ?? 0),
    "Benchmark Score",
    "#cb5f35",
    { horizontal: true }
  );
}

async function loadCompare() {
  const providers = await loadProviders();
  const providerKeys = providers.filter(item => item.enabled).map(item => item.provider);
  const query = providerKeys.length ? `?providers=${encodeURIComponent(providerKeys.join(","))}&window=24h` : "?window=24h";
  const payload = await fetchJson(`/api/dashboard/compare${query}`);
  const items = payload.compare.items || [];
  const labels = items.map(item => `${item.provider}/${item.model}`);
  const body = document.getElementById("compare-table-body");
  if (body) {
    body.innerHTML = items.map(item => `
      <tr>
        <td>${escapeHtml(item.provider)}</td>
        <td>${escapeHtml(item.model)}</td>
        <td>${formatPercent(item.availability, 1)}</td>
        <td>${formatMetric(item.avg_latency_ms, " ms")}</td>
        <td>${formatMetric(item.avg_ttft_ms, " ms")}</td>
        <td>${formatMetric(item.p95_ttft_ms, " ms")}</td>
        <td>${formatMetric(item.p95_latency_ms, " ms")}</td>
        <td>${formatMetric(item.avg_tps)}</td>
        <td>${formatMetric(item.avg_tpot_ms, " ms/token")}</td>
        <td>${formatPercent(item.goodput, 1)}</td>
        <td>${formatMetric(item.avg_cached_tokens)}</td>
        <td>${formatMetric(item.latest_eval_score, "", 4)}</td>
      </tr>
    `).join("");
  }

  initBarChart("chart-latency", labels, items.map(item => item.avg_latency_ms ?? 0), "Avg Latency", "#2364aa");
  initBarChart("chart-compare-p95-latency", labels, items.map(item => item.p95_latency_ms ?? 0), "P95 Latency", "#7a9e9f");
  initGroupedBarChart(
    "chart-compare-ttft",
    labels,
    [
      { name: "Avg TTFT", values: items.map(item => item.avg_ttft_ms ?? 0) },
      { name: "P95 TTFT", values: items.map(item => item.p95_ttft_ms ?? 0) },
    ],
    ["#3da35d", "#ff7f51"]
  );
  initGroupedBarChart(
    "chart-compare-efficiency",
    labels,
    [
      { name: "Avg TPS", values: items.map(item => item.avg_tps ?? 0) },
      { name: "Avg TPOT", values: items.map(item => item.avg_tpot_ms ?? 0) },
    ],
    ["#ffb000", "#6f4e7c"]
  );
}

function buildEvalSetBadges(item) {
  const badges = [];
  badges.push(`<span class="badge badge-${escapeHtml(item.source_type)}">${escapeHtml(item.source_type)}</span>`);
  if ((item.dataset_path || "").includes("datasets/uploaded")) {
    badges.push(`<span class="badge badge-uploaded">uploaded</span>`);
  }
  if (!item.enabled) {
    badges.push(`<span class="badge badge-disabled">disabled</span>`);
  }
  return badges.join("");
}

async function loadEvals() {
  const [setsPayload, resultsPayload] = await Promise.all([
    fetchJson("/api/eval-sets"),
    fetchJson("/api/evals/results?limit=10"),
  ]);

  const sets = setsPayload.items || [];
  const results = resultsPayload.items || [];

  const setRoot = document.getElementById("eval-set-list");
  const setEmpty = document.getElementById("eval-set-empty");
  if (setRoot) {
    setRoot.innerHTML = sets.map(item => `
      <article class="eval-set-item">
        <div class="eval-set-title">
          <strong>${escapeHtml(item.eval_name)}</strong>
          ${buildEvalSetBadges(item)}
        </div>
        <div class="meta">${escapeHtml(item.eval_key)} · ${escapeHtml(item.dataset_path)}</div>
        <div class="meta">创建时间：${escapeHtml(formatDateTime(item.created_at))}</div>
      </article>
    `).join("");
  }
  if (setEmpty) {
    setEmpty.style.display = sets.length ? "none" : "block";
  }

  const resultRoot = document.getElementById("eval-results");
  if (!resultRoot) {
    return;
  }
  resultRoot.innerHTML = results.length ? results.map(item => {
    const failures = (item.failures || []).slice(0, 3).map(failure => `
      <div class="failure">
        <div><strong>${escapeHtml(failure.case_id)}</strong> · ${escapeHtml(failure.scoring)}</div>
        <div>Reason: ${escapeHtml(failure.reason)}</div>
        <div>Prompt: <code>${escapeHtml(failure.prompt)}</code></div>
        <div>Expected: <code>${escapeHtml(JSON.stringify(failure.expected))}</code></div>
        <div>Output: <code>${escapeHtml(failure.output)}</code></div>
      </div>
    `).join("");
    return `
      <article class="result">
        <div class="meta">${escapeHtml(formatDateTime(item.created_at))} · ${escapeHtml(item.eval_set)} · ${escapeHtml(item.provider)}/${escapeHtml(item.model)}</div>
        <div><strong>Score:</strong> ${formatMetric(item.score, "", 4)} (${escapeHtml(item.passed)}/${escapeHtml(item.total)})</div>
        <div class="failures">${failures || "<div class=\"empty-state\">没有失败样本。</div>"}</div>
      </article>
    `;
  }).join("") : `<div class="empty-state">暂无 eval 结果。</div>`;
}

document.addEventListener("DOMContentLoaded", async () => {
  const page = document.body.dataset.page;
  try {
    if (page === "index") {
      await loadDashboard();
    } else if (page === "compare") {
      await loadCompare();
    } else if (page === "evals") {
      await loadEvals();
    }
  } catch (error) {
    console.error(error);
  }
});
