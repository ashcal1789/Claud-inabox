/**
 * main.js
 * -------
 * Glass-Box Language Machine — index page logic.
 *
 * Loads the most recent generation JSON from /data/generations/,
 * renders the sentence list, and handles the provenance panel.
 *
 * Supports ?run=FILENAME to load a specific generation run
 * (used by archive links).
 *
 * All data is read from static JSON files — no server required.
 */

(function () {
  "use strict";

  const GEN_INDEX_URL = "data/generation_index.json";

  const sentenceList  = document.getElementById("sentence-list");
  const runMeta       = document.getElementById("run-meta");
  const loadingEl     = document.getElementById("loading");
  const errorEl       = document.getElementById("error");
  const panel         = document.getElementById("provenance-panel");
  const panelClose    = document.getElementById("panel-close");
  const panelSentence = document.getElementById("panel-sentence");
  const panelFrags    = document.getElementById("panel-fragments");

  // ------------------------------------------------------------------
  // Fetch helpers
  // ------------------------------------------------------------------

  async function fetchJSON(url) {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status} fetching ${url}`);
    return resp.json();
  }

  // ------------------------------------------------------------------
  // Render sentence list
  // ------------------------------------------------------------------

  function renderSentences(generation) {
    loadingEl.hidden = true;

    // Run metadata line
    const d = new Date(generation.run_date);
    const dateStr = d.toLocaleDateString("en-US", {
      weekday: "long", year: "numeric", month: "long", day: "numeric"
    });
    runMeta.textContent =
      `${dateStr}  ·  run ${generation.run_id}  ·  seed ${generation.seed}`;

    // Sentences
    for (const sent of generation.sentences) {
      const li   = document.createElement("li");
      li.dataset.id = sent.id;

      const span = document.createElement("span");
      span.className = "sentence-text";
      span.textContent = sent.sentence;

      li.appendChild(span);
      li.addEventListener("click", () => openPanel(sent));
      sentenceList.appendChild(li);
    }
  }

  // ------------------------------------------------------------------
  // Provenance panel
  // ------------------------------------------------------------------

  function openPanel(sent) {
    panelSentence.textContent = sent.sentence;
    panelFrags.innerHTML = "";

    for (const frag of sent.fragments) {
      const card = document.createElement("div");
      card.className = "fragment-card";

      // Role label
      const roleEl = document.createElement("div");
      roleEl.className = "fragment-role";
      roleEl.textContent = frag.role;
      card.appendChild(roleEl);

      // Source citation
      const sourceEl = document.createElement("div");
      sourceEl.className = "fragment-source";
      const yearStr = frag.year < 0
        ? `${Math.abs(frag.year)} BCE`
        : String(frag.year);
      sourceEl.innerHTML =
        `<strong>${escapeHTML(frag.title)}</strong>` +
        `<span class="source-meta"> — ${escapeHTML(frag.author)}, ${yearStr}</span>`;
      card.appendChild(sourceEl);

      // Character offsets (machine-readable provenance anchor)
      const offsetEl = document.createElement("div");
      offsetEl.className = "fragment-offsets";
      offsetEl.textContent =
        `corpus/${frag.slug}.txt  chars ${frag.char_start}–${frag.char_end}`;
      card.appendChild(offsetEl);

      // Fragment text (highlighted)
      const textEl = document.createElement("div");
      textEl.className = "fragment-text";
      textEl.innerHTML = `<mark>${escapeHTML(frag.text)}</mark>`;
      card.appendChild(textEl);

      panelFrags.appendChild(card);
    }

    panel.hidden = false;
    panel.scrollTop = 0;
  }

  function closePanel() {
    panel.hidden = true;
  }

  panelClose.addEventListener("click", closePanel);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) closePanel();
  });

  // ------------------------------------------------------------------
  // Utility
  // ------------------------------------------------------------------

  function escapeHTML(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showError(msg) {
    loadingEl.hidden = true;
    errorEl.hidden   = false;
    errorEl.textContent = msg;
  }

  // ------------------------------------------------------------------
  // Boot
  // ------------------------------------------------------------------

  async function init() {
    try {
      // Check for ?run=FILENAME to load a specific run from the archive
      const params  = new URLSearchParams(window.location.search);
      const runFile = params.get("run");

      if (runFile) {
        // Sanitise: only allow alphanumeric, underscores, hyphens, dots
        const safe = runFile.replace(/[^a-zA-Z0-9_\-\.]/g, "");
        const generation = await fetchJSON(`data/generations/${safe}`);
        renderSentences(generation);
      } else {
        // Load the most recent run
        const index = await fetchJSON(GEN_INDEX_URL);
        if (!index || !index.runs || index.runs.length === 0) {
          showError("No generation runs found.");
          return;
        }
        const latestRun = index.runs[0];
        const generation = await fetchJSON(`data/generations/${latestRun.file}`);
        renderSentences(generation);
      }
    } catch (err) {
      showError(`Could not load generation data: ${err.message}`);
    }
  }

  init();
})();
