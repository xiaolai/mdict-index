import { renderAnalysis } from "./analysis.js";

const $ = (selector) => document.querySelector(selector);
const out = $("#out");
const text = $("#text");
const possible = $("#possible");
let generation = 0; // the latest request; a response to any earlier one is dropped
let last = null;    // the latest result, redrawn when "possible" is switched

function draw() {
  if (last) out.innerHTML = renderAnalysis(last.text, last.result, { possible: possible.checked });
}

async function run() {
  const current = ++generation;
  const value = text.value;
  if (!value.trim()) return;
  out.innerHTML = `<p class="results__note">分析中… Analysing…</p>`;
  try {
    const res = await fetch("/api/analyze", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: value }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`);
    const result = await res.json();
    if (current !== generation) return;
    last = { text: value, result };
    draw();
  } catch (error) {
    if (current !== generation) return;
    out.innerHTML = `<p class="results__note">出错了 Something went wrong: ${String(error.message)
      .replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c])}</p>`;
  }
}

$("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run();
});
possible.addEventListener("change", draw);
