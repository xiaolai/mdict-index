// The recommendation tab strip: WAI-ARIA tabs over a list of panels. Holds no state:
// the selected tab is read through `current()` and changed through `onSelect(key)`, both
// supplied by app.js, which re-imports itself with fresh state per test while this
// module loads once.
import { el } from "./view.js";

// WAI-ARIA tabs: one tab stop, arrow keys move between tabs, panels follow selection.
// Returns the tab strip and panel elements, plus `select(key)` and `reveal()`.
export function tabController(panels, current, onSelect) {
  const tabs = panels.map((p) =>
    el(
      "button",
      {
        type: "button",
        role: "tab",
        id: `tab-${p.key}`,
        class: "tab",
        "aria-controls": `panel-${p.key}`,
        onclick: () => select(p.key),
      },
      p.tab[0],
      el("span", { class: "tab__en", textContent: p.tab[1] }),
      el("span", { class: "tab__n", textContent: String(p.count) }),
    ),
  );
  const bodies = panels.map((p) => {
    const body = p.body();
    body.id = `panel-${p.key}`;
    body.tabIndex = 0;
    body.setAttribute("role", "tabpanel");
    body.setAttribute("aria-labelledby", `tab-${p.key}`);
    return body;
  });
  // On narrow screens the strip scrolls sideways; keep the active tab in view.
  // Sets scrollLeft only: scrollIntoView would also scroll the page.
  const reveal = () => {
    const t = tabs[panels.findIndex((p) => p.key === current())];
    const strip = t.parentElement;
    strip.scrollLeft = t.offsetLeft - (strip.clientWidth - t.offsetWidth) / 2;
  };
  function select(key, focus = false) {
    onSelect(key);
    panels.forEach((p, i) => {
      const on = p.key === key;
      tabs[i].setAttribute("aria-selected", String(on));
      tabs[i].tabIndex = on ? 0 : -1;
      bodies[i].hidden = !on;
      if (on && focus) tabs[i].focus();
    });
    reveal();
  }
  const onKey = (e) => {
    const i = panels.findIndex((p) => p.key === current());
    const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: panels.length - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    select(panels[(next + panels.length) % panels.length].key, true);
  };
  const strip = el("div", { class: "tabs", role: "tablist", "aria-label": "推荐分类 Recommendation categories", onkeydown: onKey }, ...tabs);
  return { strip, bodies, select, reveal };
}
