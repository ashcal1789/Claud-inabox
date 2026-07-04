#!/usr/bin/env python3
"""
build_index.py
--------------
Scans data/generations/*.json and writes data/generation_index.json —
a lightweight index used by the site to discover available generation runs.

Also copies the latest generation JSON to site/data/ so GitHub Pages
can serve it without needing a server-side directory listing.

Run after every generation:
    python3 engine/build_index.py
"""

import json
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GEN_DIR   = REPO_ROOT / "data" / "generations"
DATA_DIR  = REPO_ROOT / "data"
SITE_DATA = REPO_ROOT / "site" / "data"

def main():
    SITE_DATA.mkdir(parents=True, exist_ok=True)

    gen_files = sorted(GEN_DIR.glob("*.json"), reverse=True)

    runs = []
    for gf in gen_files:
        with open(gf, encoding="utf-8") as f:
            gen = json.load(f)
        runs.append({
            "file":    gf.name,
            "run_id":  gen.get("run_id", gf.stem),
            "date":    gen.get("run_date", ""),
            "count":   gen.get("count", 0),
            "seed":    gen.get("seed", None),
        })

    index = {
        "updated": runs[0]["date"] if runs else "",
        "total_runs": len(runs),
        "runs": runs,
    }

    # Write to data/ (raw data endpoint)
    index_path = DATA_DIR / "generation_index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    # Mirror to site/data/ so GitHub Pages serves it
    site_index_path = SITE_DATA / "generation_index.json"
    shutil.copy(index_path, site_index_path)

    # Mirror all generation JSONs to site/data/generations/
    site_gen_dir = SITE_DATA / "generations"
    site_gen_dir.mkdir(parents=True, exist_ok=True)
    for gf in gen_files:
        shutil.copy(gf, site_gen_dir / gf.name)

    # Mirror corpus_index.json
    shutil.copy(DATA_DIR / "corpus_index.json", SITE_DATA / "corpus_index.json")

    # Mirror verification report if it exists
    vr = DATA_DIR / "verification_report.json"
    if vr.exists():
        shutil.copy(vr, SITE_DATA / "verification_report.json")

    print(f"Index written: {len(runs)} runs")
    if runs:
        print(f"Latest: {runs[0]['file']}")

if __name__ == "__main__":
    main()
