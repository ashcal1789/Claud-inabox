/**
 * archive.js
 * ----------
 * Glass-Box Language Machine — archive page logic.
 *
 * Loads generation_index.json and renders a list of all past runs
 * with links to view the generation and the raw provenance JSON.
 */

(function () {
  "use strict";

  const GEN_INDEX_URL = "data/generation_index.json";

  const archiveList = document.getElementById("archive-list");
  const loadingEl   = document.getElementById("loading");

  function escapeHTML(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  async function init() {
    try {
      const index = await fetch(GEN_INDEX_URL).then(r => r.json());
      loadingEl.hidden = true;

      if (!index.runs || index.runs.length === 0) {
        archiveList.innerHTML = "<li>No runs yet.</li>";
        return;
      }

      for (const run of index.runs) {
        const li = document.createElement("li");

        const d = new Date(run.date);
        const dateStr = d.toLocaleDateString("en-US", {
          year: "numeric", month: "long", day: "numeric"
        });

        const dateEl = document.createElement("span");
        dateEl.className = "archive-date";
        dateEl.textContent = dateStr;

        const linksEl = document.createElement("div");
        linksEl.className = "archive-links";

        // Link to view this run on the main page
        const viewLink = document.createElement("a");
        viewLink.href = `index.html?run=${encodeURIComponent(run.file)}`;
        viewLink.textContent = `${run.count} sentences`;

        // Link to raw JSON
        const jsonLink = document.createElement("a");
        jsonLink.href = `data/generations/${escapeHTML(run.file)}`;
        jsonLink.textContent = "raw JSON";
        jsonLink.target = "_blank";
        jsonLink.rel = "noopener";

        linksEl.appendChild(viewLink);
        linksEl.appendChild(jsonLink);

        li.appendChild(dateEl);
        li.appendChild(linksEl);
        archiveList.appendChild(li);
      }
    } catch (err) {
      loadingEl.textContent = `Error loading archive: ${err.message}`;
    }
  }

  init();
})();
