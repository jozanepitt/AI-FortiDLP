const $ = (id) => document.getElementById(id);

async function loadCanned() {
  const sel = $("canned-select");
  const res = await fetch("/api/canned");
  const items = await res.json();
  for (const item of items) {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.label;
    sel.appendChild(opt);
  }
}

function renderAnswer(text) {
  $("answer").textContent = text;
}

function renderTrace(trace) {
  const wrap = $("trace-wrap");
  if (!trace || trace.length === 0) {
    wrap.hidden = true;
    return;
  }
  wrap.hidden = false;
  $("trace").textContent = JSON.stringify(trace, null, 2);
}

async function runCanned() {
  const id = $("canned-select").value;
  if (!id) return;
  const btn = $("canned-run");
  btn.disabled = true;
  renderAnswer("Running...");
  renderTrace(null);
  try {
    const res = await fetch(`/api/canned/${encodeURIComponent(id)}`, {
      method: "POST",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderAnswer(JSON.stringify(data.result, null, 2));
  } catch (err) {
    renderAnswer(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

async function ask() {
  const question = $("question").value.trim();
  if (!question) return;
  const btn = $("ask-btn");
  btn.disabled = true;
  renderAnswer("Thinking...");
  renderTrace(null);
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(`HTTP ${res.status}: ${detail}`);
    }
    const data = await res.json();
    renderAnswer(data.answer || "(no answer)");
    renderTrace(data.trace);
  } catch (err) {
    renderAnswer(`Error: ${err.message}`);
  } finally {
    btn.disabled = false;
  }
}

$("canned-run").addEventListener("click", runCanned);
$("ask-btn").addEventListener("click", ask);
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) ask();
});

loadCanned();
