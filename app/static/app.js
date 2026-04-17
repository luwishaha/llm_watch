async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data?.error?.message || `Request failed: ${response.status}`);
  }
  return data;
}

function formatMetric(value, suffix = "") {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${value}${suffix}`;
}

function initBarChart(elementId, labels, values, name, color) {
  const target = document.getElementById(elementId);
  if (!target) {
    return;
  }
  const chart = echarts.init(target);
  chart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: "category", data: labels, axisLabel: { rotate: 0 } },
    yAxis: { type: "value" },
    series: [{ name, type: "bar", data: values, itemStyle: { color, borderRadius: [8, 8, 0, 0] } }],
  });
}

async function loadDashboard() {
  const payload = await fetchJson("/api/dashboard/summary");
  const summary = payload.summary;
  const availability = summary.availability_24h.filter(item => item.value !== null);
  const ttft = summary.avg_ttft_24h.filter(item => item.value !== null);
  const tps = summary.avg_tps_24h.filter(item => item.value !== null);
  const evals = summary.latest_custom_eval.filter(item => item.score !== null);

  const bestAvailability = availability.sort((a, b) => b.value - a.value)[0];
  const bestTtft = ttft.sort((a, b) => a.value - b.value)[0];
  const bestTps = tps.sort((a, b) => b.value - a.value)[0];
  const bestEval = evals.sort((a, b) => b.score - a.score)[0];

  document.getElementById("metric-availability").textContent = bestAvailability ? `${bestAvailability.provider} ${Math.round(bestAvailability.value * 100)}%` : "-";
  document.getElementById("metric-ttft").textContent = bestTtft ? `${bestTtft.provider} ${bestTtft.value} ms` : "-";
  document.getElementById("metric-tps").textContent = bestTps ? `${bestTps.provider} ${bestTps.value}` : "-";
  document.getElementById("metric-eval").textContent = bestEval ? `${bestEval.provider} ${bestEval.score}` : "-";

  initBarChart("chart-availability", summary.availability_24h.map(i => i.provider), summary.availability_24h.map(i => i.value === null ? 0 : i.value), "Availability", "#cb5f35");
  initBarChart("chart-ttft", summary.avg_ttft_24h.map(i => i.provider), summary.avg_ttft_24h.map(i => i.value === null ? 0 : i.value), "TTFT", "#6a8491");
  initBarChart("chart-tps", summary.avg_tps_24h.map(i => i.provider), summary.avg_tps_24h.map(i => i.value === null ? 0 : i.value), "TPS", "#8c6f56");

  const list = document.getElementById("latest-evals");
  list.innerHTML = summary.latest_custom_eval.map(item => `<li><strong>${item.provider}</strong> <span>${formatMetric(item.score)}</span></li>`).join("");
}

async function loadCompare() {
  const payload = await fetchJson("/api/dashboard/compare?providers=deepseek,dashscope,qianfan&window=24h");
  const items = payload.compare.items;
  const body = document.getElementById("compare-table-body");
  body.innerHTML = items.map(item => `
    <tr>
      <td>${item.provider}</td>
      <td>${item.model}</td>
      <td>${formatMetric(item.availability)}</td>
      <td>${formatMetric(item.avg_latency_ms, " ms")}</td>
      <td>${formatMetric(item.avg_ttft_ms, " ms")}</td>
      <td>${formatMetric(item.avg_tps)}</td>
      <td>${formatMetric(item.avg_cached_tokens)}</td>
      <td>${formatMetric(item.latest_eval_score)}</td>
    </tr>
  `).join("");

  initBarChart("chart-latency", items.map(i => i.provider), items.map(i => i.avg_latency_ms || 0), "Latency", "#2364aa");
  initBarChart("chart-compare-ttft", items.map(i => i.provider), items.map(i => i.avg_ttft_ms || 0), "TTFT", "#3da35d");
  initBarChart("chart-compare-tps", items.map(i => i.provider), items.map(i => i.avg_tps || 0), "TPS", "#ff7f51");
  initBarChart("chart-eval-score", items.map(i => i.provider), items.map(i => i.latest_eval_score || 0), "Eval Score", "#7d53de");
}

async function loadEvals() {
  const payload = await fetchJson("/api/evals/results?limit=10");
  const root = document.getElementById("eval-results");
  root.innerHTML = payload.items.map(item => {
    const failures = (item.failures || []).slice(0, 3).map(failure => `
      <div class="failure">
        <div><strong>${failure.case_id}</strong> · ${failure.scoring}</div>
        <div>Reason: ${failure.reason}</div>
        <div>Prompt: <code>${failure.prompt}</code></div>
        <div>Expected: <code>${JSON.stringify(failure.expected)}</code></div>
        <div>Output: <code>${failure.output}</code></div>
      </div>
    `).join("");
    return `
      <article class="result">
        <div class="meta">${item.created_at} · ${item.eval_set} · ${item.provider}/${item.model}</div>
        <div><strong>Score:</strong> ${item.score} (${item.passed}/${item.total})</div>
        <div class="failures">${failures || "<div>没有失败样本。</div>"}</div>
      </article>
    `;
  }).join("");
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
