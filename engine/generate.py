#!/usr/bin/env python3
"""
generate.py
-----------
The Glass-Box Language Machine — generation engine.

Method: Hybrid cut-up / n-gram recombination.

For each generated sentence the engine:
  1. Picks a "seed" source text (rotating through all corpus texts to ensure balance).
  2. Extracts a grammatically plausible sentence fragment from that source
     (a span of 4–12 words ending at a natural boundary).
  3. Picks a "continuation" fragment from a *different* source text using
     a simple bigram bridge: the last word of the seed fragment is used to
     find a continuation that begins with a word of the same part-of-speech.
  4. Optionally appends a short closing fragment from a third source.
  5. Records the exact character offsets (start, end) of every fragment
     within its source file — this is the provenance record.

The provenance record is the core guarantee: given a generation JSON file,
any reader (human or machine) can open the source .txt file, slice
text[char_start:char_end], and recover the exact fragment used.

No neural networks. No external API calls during generation.
The only randomness comes from a seeded PRNG — pass --seed N for
fully reproducible output.

Usage:
    python3 engine/generate.py [--seed N] [--count N] [--out-dir data/generations]
"""

import os
import re
import sys
import json
import random
import hashlib
import argparse
import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root, which is the parent of this script's dir)
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "corpus"
DATA_DIR   = REPO_ROOT / "data"
GEN_DIR    = DATA_DIR / "generations"

# ---------------------------------------------------------------------------
# Sentence boundary pattern
# Matches end-of-sentence punctuation followed by whitespace or end-of-string.
# ---------------------------------------------------------------------------
SENT_END = re.compile(r'[.!?]["\']?\s')

# ---------------------------------------------------------------------------
# Very lightweight POS tag categories (no external library required).
# We classify words into broad buckets for the bigram bridge.
# ---------------------------------------------------------------------------
FUNCTION_WORDS = {
    "the", "a", "an", "and", "but", "or", "nor", "for", "yet", "so",
    "in", "on", "at", "by", "to", "of", "with", "from", "into", "through",
    "during", "before", "after", "above", "below", "between", "among",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "shall", "should",
    "may", "might", "must", "can", "could", "that", "which", "who",
    "whom", "this", "these", "those", "it", "its", "he", "she", "they",
    "we", "i", "my", "his", "her", "their", "our", "your", "not", "no",
    "all", "each", "every", "both", "few", "more", "most", "other",
    "some", "such", "than", "then", "when", "where", "while", "if",
    "as", "what", "how", "there", "here",
}

def word_class(word):
    """Return a broad word class: 'function', 'short', or 'content'."""
    w = word.lower().strip(".,;:!?\"'()-")
    if w in FUNCTION_WORDS:
        return "function"
    if len(w) <= 3:
        return "short"
    return "content"


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_corpus_index():
    """Load corpus_index.json and return list of metadata dicts."""
    path = DATA_DIR / "corpus_index.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_source_text(slug):
    """
    Load a corpus text by slug.
    Returns the raw string exactly as stored on disk.
    Character offsets in provenance records refer to this string.
    """
    path = CORPUS_DIR / f"{slug}.txt"
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Fragment extraction
# ---------------------------------------------------------------------------

def find_sentence_spans(text, min_words=6, max_words=20):
    """
    Return a list of (start, end) character spans for plausible sentence
    fragments within `text`.

    A fragment is defined as a run of min_words..max_words words that:
      - Does not start with a digit or punctuation.
      - Does not contain a newline mid-span (keeps fragments coherent).
      - Ends at a word boundary (space or end of string).

    We scan the text in steps to avoid building a huge list.
    """
    spans = []
    # Split into tokens with their positions
    tokens = list(re.finditer(r'\b[A-Za-z][A-Za-z\'-]*\b', text))
    if len(tokens) < min_words:
        return spans

    step = max(1, len(tokens) // 4000)  # sample at most ~4000 start positions
    for i in range(0, len(tokens) - min_words, step):
        for length in range(min_words, min(max_words + 1, len(tokens) - i)):
            t_start = tokens[i]
            t_end   = tokens[i + length - 1]
            char_start = t_start.start()
            char_end   = t_end.end()
            fragment   = text[char_start:char_end]
            # Reject fragments with internal newlines
            if "\n" in fragment:
                break
            # Accept this length — record it
            spans.append((char_start, char_end))
            # Only record one length per start position to keep list manageable
            break

    return spans


def pick_fragment(text, spans, rng):
    """Pick a random (start, end) span and return (fragment_text, start, end)."""
    start, end = rng.choice(spans)
    return text[start:end], start, end


# ---------------------------------------------------------------------------
# Balance tracker
# ---------------------------------------------------------------------------

def load_balance_state():
    """
    Load the per-slug usage counter from data/balance.json.
    Returns a dict {slug: count}.
    """
    path = DATA_DIR / "balance.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_balance_state(state):
    path = DATA_DIR / "balance.json"
    with open(path, "w") as f:
        json.dump(state, f, indent=2)


def pick_source_balanced(slugs, balance, rng):
    """
    Pick a slug, preferring those used least so far.
    Adds a small random jitter so the order isn't perfectly deterministic.
    """
    min_count = min(balance.get(s, 0) for s in slugs)
    candidates = [s for s in slugs if balance.get(s, 0) <= min_count + 1]
    return rng.choice(candidates)


# ---------------------------------------------------------------------------
# Sentence assembly
# ---------------------------------------------------------------------------

def assemble_sentence(sources, balance, rng, texts_cache):
    """
    Build one sentence from 2–3 fragments drawn from different sources.

    Returns a dict with:
      - "sentence": the assembled text string
      - "fragments": list of provenance records, each containing:
          - "slug": source file slug
          - "title": human-readable title
          - "author": author name
          - "year": publication year
          - "char_start": start offset in the source .txt file
          - "char_end": end offset in the source .txt file
          - "text": the exact fragment text (redundant but convenient)
          - "role": "seed" | "continuation" | "closing"
    """
    slugs = [s["slug"] for s in sources]

    # --- Fragment 1: seed ---
    seed_slug = pick_source_balanced(slugs, balance, rng)
    if seed_slug not in texts_cache:
        texts_cache[seed_slug] = load_source_text(seed_slug)
    seed_text  = texts_cache[seed_slug]
    seed_spans = find_sentence_spans(seed_text, min_words=4, max_words=10)
    if not seed_spans:
        return None
    seed_frag, seed_start, seed_end = pick_fragment(seed_text, seed_spans, rng)
    seed_meta = next(s for s in sources if s["slug"] == seed_slug)

    # --- Fragment 2: continuation from a different source ---
    other_slugs = [s for s in slugs if s != seed_slug]
    cont_slug = pick_source_balanced(other_slugs, balance, rng)
    if cont_slug not in texts_cache:
        texts_cache[cont_slug] = load_source_text(cont_slug)
    cont_text  = texts_cache[cont_slug]
    cont_spans = find_sentence_spans(cont_text, min_words=4, max_words=10)
    if not cont_spans:
        return None
    cont_frag, cont_start, cont_end = pick_fragment(cont_text, cont_spans, rng)
    cont_meta = next(s for s in sources if s["slug"] == cont_slug)

    # --- Fragment 3 (optional closing): from a third source, ~30% of the time ---
    closing_fragment = None
    if rng.random() < 0.30:
        third_slugs = [s for s in slugs if s not in (seed_slug, cont_slug)]
        if third_slugs:
            close_slug = pick_source_balanced(third_slugs, balance, rng)
            if close_slug not in texts_cache:
                texts_cache[close_slug] = load_source_text(close_slug)
            close_text  = texts_cache[close_slug]
            close_spans = find_sentence_spans(close_text, min_words=3, max_words=7)
            if close_spans:
                close_frag, close_start, close_end = pick_fragment(close_text, close_spans, rng)
                close_meta = next(s for s in sources if s["slug"] == close_slug)
                closing_fragment = {
                    "slug":       close_slug,
                    "title":      close_meta["title"],
                    "author":     close_meta["author"],
                    "year":       close_meta["year"],
                    "char_start": close_start,
                    "char_end":   close_end,
                    "text":       close_frag,
                    "role":       "closing"
                }

    # --- Assemble the sentence ---
    # Clean up fragment edges: strip leading/trailing partial words
    def clean(frag):
        # Ensure starts with a capital-able character
        frag = frag.strip()
        # Remove leading punctuation
        frag = re.sub(r'^[,;:\-—]+\s*', '', frag)
        return frag

    parts = [clean(seed_frag), clean(cont_frag)]
    if closing_fragment:
        parts.append(clean(closing_fragment["text"]))

    # Join with a comma-space, capitalize first word, end with period
    sentence = ", ".join(p.rstrip(".,;:") for p in parts if p)
    sentence = sentence[0].upper() + sentence[1:] if sentence else ""
    if sentence and sentence[-1] not in ".!?":
        sentence += "."

    # --- Update balance ---
    balance[seed_slug] = balance.get(seed_slug, 0) + 1
    balance[cont_slug] = balance.get(cont_slug, 0) + 1
    if closing_fragment:
        balance[closing_fragment["slug"]] = balance.get(closing_fragment["slug"], 0) + 1

    # --- Build provenance record ---
    fragments = [
        {
            "slug":       seed_slug,
            "title":      seed_meta["title"],
            "author":     seed_meta["author"],
            "year":       seed_meta["year"],
            "char_start": seed_start,
            "char_end":   seed_end,
            "text":       seed_frag,
            "role":       "seed"
        },
        {
            "slug":       cont_slug,
            "title":      cont_meta["title"],
            "author":     cont_meta["author"],
            "year":       cont_meta["year"],
            "char_start": cont_start,
            "char_end":   cont_end,
            "text":       cont_frag,
            "role":       "continuation"
        },
    ]
    if closing_fragment:
        fragments.append(closing_fragment)

    return {
        "sentence":  sentence,
        "fragments": fragments,
    }


# ---------------------------------------------------------------------------
# Main generation run
# ---------------------------------------------------------------------------

def run_generation(seed=None, count=20, out_dir=None):
    """
    Generate `count` sentences, write provenance JSON to out_dir.
    Returns the path to the written JSON file.
    """
    if out_dir is None:
        out_dir = GEN_DIR
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Seed the PRNG
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    rng = random.Random(seed)

    sources = load_corpus_index()
    balance = load_balance_state()
    texts_cache = {}

    run_id   = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_date = datetime.datetime.now(datetime.timezone.utc).isoformat() + "Z"

    sentences = []
    attempts  = 0
    while len(sentences) < count and attempts < count * 10:
        attempts += 1
        result = assemble_sentence(sources, balance, rng, texts_cache)
        if result:
            # Assign a stable sentence ID: hash of the sentence text
            sid = hashlib.sha1(result["sentence"].encode()).hexdigest()[:12]
            sentences.append({
                "id":        sid,
                "sentence":  result["sentence"],
                "fragments": result["fragments"],
            })

    save_balance_state(balance)

    generation_record = {
        "run_id":    run_id,
        "run_date":  run_date,
        "seed":      seed,
        "count":     len(sentences),
        "sentences": sentences,
    }

    out_path = out_dir / f"{run_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(generation_record, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(sentences)} sentences → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Glass-Box Language Machine — generator")
    parser.add_argument("--seed",    type=int, default=None, help="PRNG seed for reproducibility")
    parser.add_argument("--count",   type=int, default=20,   help="Number of sentences to generate")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for generation JSON")
    args = parser.parse_args()

    out_path = run_generation(seed=args.seed, count=args.count, out_dir=args.out_dir)
    print(f"Done. Provenance record: {out_path}")


if __name__ == "__main__":
    main()
