#!/usr/bin/env python3
"""
verify_provenance.py
--------------------
Automated provenance verification for the Glass-Box Language Machine.

What this checks (for EVERY sentence in EVERY generation file):
  1. The recorded char_start and char_end offsets are valid integers within
     the bounds of the source corpus file.
  2. corpus_file[char_start:char_end] exactly equals the recorded fragment
     text field — byte-for-byte, no approximation.
  3. Every slug referenced in a provenance record exists in corpus_index.json
     and the corresponding .txt file is present on disk.
  4. No two fragments in the same sentence share the same source slug
     (the engine's own rule: each fragment must come from a distinct source).
  5. The sentence field is non-empty and is a string.

This is not sampling. Every fragment in every generation file is checked.

Exit codes:
  0 — all checks passed
  1 — one or more checks failed

Results are written to data/verification_report.json, which is committed
alongside each generation run so the repo always contains a current
verification state.

Usage:
    python3 engine/verify_provenance.py [--gen-dir data/generations]
"""

import os
import sys
import json
import datetime
from pathlib import Path

REPO_ROOT  = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "corpus"
DATA_DIR   = REPO_ROOT / "data"
GEN_DIR    = DATA_DIR / "generations"


def load_corpus_index():
    path = DATA_DIR / "corpus_index.json"
    with open(path, encoding="utf-8") as f:
        return {entry["slug"]: entry for entry in json.load(f)}


def load_source_text(slug, cache):
    if slug not in cache:
        path = CORPUS_DIR / f"{slug}.txt"
        with open(path, encoding="utf-8") as f:
            cache[slug] = f.read()
    return cache[slug]


def verify_generation_file(gen_path, corpus_index, text_cache):
    """
    Verify all provenance records in a single generation JSON file.

    Returns a dict:
      {
        "file": str,
        "sentences_checked": int,
        "fragments_checked": int,
        "failures": [ { "sentence_id", "fragment_role", "slug", "error" }, ... ],
        "passed": bool
      }
    """
    with open(gen_path, encoding="utf-8") as f:
        gen = json.load(f)

    failures = []
    sentences_checked = 0
    fragments_checked = 0

    for sent in gen.get("sentences", []):
        sentences_checked += 1
        sid = sent.get("id", "?")

        # Check 5: sentence is a non-empty string
        if not isinstance(sent.get("sentence"), str) or not sent["sentence"].strip():
            failures.append({
                "sentence_id": sid,
                "fragment_role": "N/A",
                "slug": "N/A",
                "error": "sentence field is empty or not a string"
            })

        slugs_seen = []
        for frag in sent.get("fragments", []):
            fragments_checked += 1
            slug  = frag.get("slug", "")
            role  = frag.get("role", "?")
            start = frag.get("char_start")
            end   = frag.get("char_end")
            recorded_text = frag.get("text", "")

            # Check 3: slug exists in corpus index and on disk
            if slug not in corpus_index:
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": f"slug '{slug}' not found in corpus_index.json"
                })
                continue

            corpus_file = CORPUS_DIR / f"{slug}.txt"
            if not corpus_file.exists():
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": f"corpus file '{slug}.txt' not found on disk"
                })
                continue

            # Check 1: offsets are valid integers
            if not isinstance(start, int) or not isinstance(end, int):
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": f"char_start ({start!r}) or char_end ({end!r}) is not an integer"
                })
                continue

            source_text = load_source_text(slug, text_cache)

            if start < 0 or end > len(source_text) or start >= end:
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": (
                        f"offsets [{start}:{end}] out of bounds "
                        f"(source length={len(source_text)})"
                    )
                })
                continue

            # Check 2: exact text match
            actual_text = source_text[start:end]
            if actual_text != recorded_text:
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": (
                        f"text mismatch at [{start}:{end}]: "
                        f"expected {recorded_text!r}, "
                        f"got {actual_text!r}"
                    )
                })
                continue

            # Check 4: no duplicate slugs within the same sentence
            if slug in slugs_seen:
                failures.append({
                    "sentence_id": sid,
                    "fragment_role": role,
                    "slug": slug,
                    "error": f"slug '{slug}' appears more than once in the same sentence"
                })
            slugs_seen.append(slug)

    return {
        "file":               str(gen_path.name),
        "run_id":             gen.get("run_id", "?"),
        "run_date":           gen.get("run_date", "?"),
        "sentences_checked":  sentences_checked,
        "fragments_checked":  fragments_checked,
        "failures":           failures,
        "passed":             len(failures) == 0,
    }


def main(gen_dir=None):
    if gen_dir is None:
        gen_dir = GEN_DIR
    gen_dir = Path(gen_dir)

    corpus_index = load_corpus_index()
    text_cache   = {}

    gen_files = sorted(gen_dir.glob("*.json"))
    if not gen_files:
        print("No generation files found.")
        sys.exit(0)

    results = []
    total_sentences = 0
    total_fragments = 0
    total_failures  = 0

    for gf in gen_files:
        result = verify_generation_file(gf, corpus_index, text_cache)
        results.append(result)
        total_sentences += result["sentences_checked"]
        total_fragments += result["fragments_checked"]
        total_failures  += len(result["failures"])

        status = "PASS" if result["passed"] else f"FAIL ({len(result['failures'])} errors)"
        print(f"  {result['file']:40s}  {status}")
        for f in result["failures"]:
            print(f"    ✗ sentence {f['sentence_id']} / {f['fragment_role']} / {f['slug']}: {f['error']}")

    all_passed = total_failures == 0

    report = {
        "verified_at":       datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z",
        "generation_files":  len(gen_files),
        "sentences_checked": total_sentences,
        "fragments_checked": total_fragments,
        "total_failures":    total_failures,
        "all_passed":        all_passed,
        "results":           results,
    }

    report_path = DATA_DIR / "verification_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print()
    print(f"{'='*60}")
    print(f"Files checked:     {len(gen_files)}")
    print(f"Sentences checked: {total_sentences}")
    print(f"Fragments checked: {total_fragments}")
    print(f"Failures:          {total_failures}")
    print(f"Result:            {'ALL PASSED' if all_passed else 'FAILURES DETECTED'}")
    print(f"Report written to: {report_path}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Glass-Box provenance verifier")
    parser.add_argument("--gen-dir", type=str, default=None,
                        help="Directory containing generation JSON files")
    args = parser.parse_args()
    main(gen_dir=args.gen_dir)
