// The search page's controller (scripts/lookup_ui/lookup.js) against a minimal stand-in DOM:
// out-of-order responses and failed audio playback.
import assert from "node:assert/strict";
import { test } from "node:test";

const listeners = new Map(); // "selector:event" -> handler
const element = (selector) => ({
  innerHTML: "",
  value: "",
  addEventListener: (event, handler) => listeners.set(`${selector}:${event}`, handler),
});
const elements = { "#out": element("#out"), "#q": element("#q"), "#form": element("#form"), "#define": element("#define") };
const pending = new Map(); // query -> resolve(json)

globalThis.document = {
  querySelector: (selector) => elements[selector],
  createElement: (tag) => ({ tag }),
};
globalThis.location = { search: "" };
globalThis.history = { pushState() {} };
globalThis.window = { addEventListener() {} };
globalThis.fetch = (url) => {
  const q = new URL(url, "http://x").searchParams.get("q");
  return new Promise((resolve) => pending.set(q, (json) => resolve({ ok: true, json: async () => json })));
};
globalThis.Audio = class {
  play() {
    return Promise.reject(new Error("playback refused"));
  }
};

await import("../scripts/lookup_ui/lookup.js");
const out = elements["#out"];
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function search(q) {
  elements["#q"].value = q;
  listeners.get("#form:submit")({ preventDefault() {} });
}

test("a slower earlier search never overwrites a newer one", async () => {
  search("first");
  search("second");
  pending.get("second")({ hits: [], suggestions: [] });
  await settle();
  assert.match(out.innerHTML, /second/);
  pending.get("first")({ hits: [], suggestions: [] });
  await settle();
  assert.match(out.innerHTML, /second/);
  assert.doesNotMatch(out.innerHTML, /first/);
});

test("failed audio playback is shown, not left as an unhandled rejection", async () => {
  const added = [];
  const button = { dataset: { audio: "/res/a/x.mp3" }, after: (node) => added.push(node) };
  const target = { closest: (selector) => (selector === "button[data-audio]" ? button : null) };
  await listeners.get("#out:click")({ target });
  assert.equal(added.length, 1);
  assert.match(added[0].textContent, /playback refused/);
});
