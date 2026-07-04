#!/usr/bin/env python3
"""
fetch_corpus.py
---------------
Downloads 24 curated public-domain texts from Project Gutenberg
and writes a corpus_index.json metadata file.

Run once to populate /corpus/ and /data/corpus_index.json.
"""

import os
import json
import time
import urllib.request

# ---------------------------------------------------------------------------
# Corpus manifest
# Each entry: (slug, title, author, year, gutenberg_id_or_url)
# Deliberately diverse in register and perspective.
# ---------------------------------------------------------------------------
CORPUS = [
    # Natural history / field observation
    {
        "slug": "darwin_voyage",
        "title": "The Voyage of the Beagle",
        "author": "Charles Darwin",
        "year": 1839,
        "source_url": "https://www.gutenberg.org/cache/epub/944/pg944.txt",
        "register": "natural history"
    },
    {
        "slug": "white_selborne",
        "title": "The Natural History of Selborne",
        "author": "Gilbert White",
        "year": 1789,
        "source_url": "https://www.gutenberg.org/cache/epub/1408/pg1408.txt",
        "register": "natural history"
    },
    {
        "slug": "thoreau_walden",
        "title": "Walden",
        "author": "Henry David Thoreau",
        "year": 1854,
        "source_url": "https://www.gutenberg.org/cache/epub/205/pg205.txt",
        "register": "natural history / philosophy"
    },
    # Personal letters
    {
        "slug": "keats_letters",
        "title": "Letters of John Keats to His Family and Friends",
        "author": "John Keats",
        "year": 1891,
        "source_url": "https://www.gutenberg.org/cache/epub/35698/pg35698.txt",
        "register": "personal letters"
    },
    {
        "slug": "wollstonecraft_letters",
        "title": "Letters Written During a Short Residence in Sweden, Norway, and Denmark",
        "author": "Mary Wollstonecraft",
        "year": 1796,
        "source_url": "https://www.gutenberg.org/cache/epub/3529/pg3529.txt",
        "register": "personal letters / travel"
    },
    # Philosophy
    {
        "slug": "marcus_aurelius",
        "title": "Meditations",
        "author": "Marcus Aurelius",
        "year": 180,
        "source_url": "https://www.gutenberg.org/cache/epub/2680/pg2680.txt",
        "register": "philosophy"
    },
    {
        "slug": "spinoza_ethics",
        "title": "Ethics",
        "author": "Baruch Spinoza",
        "year": 1677,
        "source_url": "https://www.gutenberg.org/cache/epub/3800/pg3800.txt",
        "register": "philosophy"
    },
    {
        "slug": "hume_understanding",
        "title": "An Enquiry Concerning Human Understanding",
        "author": "David Hume",
        "year": 1748,
        "source_url": "https://www.gutenberg.org/cache/epub/9662/pg9662.txt",
        "register": "philosophy"
    },
    # Court / trial transcripts and legal
    {
        "slug": "trial_socrates",
        "title": "The Apology of Socrates",
        "author": "Plato (trans. Benjamin Jowett)",
        "year": -399,
        "source_url": "https://www.gutenberg.org/cache/epub/1656/pg1656.txt",
        "register": "trial / philosophy"
    },
    {
        "slug": "joan_of_arc_trial",
        "title": "The Trial of Jeanne d'Arc",
        "author": "W.P. Barrett (trans.)",
        "year": 1431,
        "source_url": "https://www.gutenberg.org/cache/epub/16981/pg16981.txt",
        "register": "trial transcript"
    },
    # Ship logs / exploration
    {
        "slug": "cook_voyage",
        "title": "A Voyage Towards the South Pole and Round the World (Vol. 1)",
        "author": "James Cook",
        "year": 1777,
        "source_url": "https://www.gutenberg.org/cache/epub/15777/pg15777.txt",
        "register": "ship log / exploration"
    },
    {
        "slug": "dana_two_years",
        "title": "Two Years Before the Mast",
        "author": "Richard Henry Dana Jr.",
        "year": 1840,
        "source_url": "https://www.gutenberg.org/cache/epub/2055/pg2055.txt",
        "register": "ship log / memoir"
    },
    # Folk tales
    {
        "slug": "grimm_tales",
        "title": "Grimms' Fairy Tales",
        "author": "Jacob and Wilhelm Grimm",
        "year": 1812,
        "source_url": "https://www.gutenberg.org/cache/epub/2591/pg2591.txt",
        "register": "folk tales"
    },
    {
        "slug": "arabian_nights",
        "title": "The Arabian Nights Entertainments",
        "author": "Anonymous (trans. Andrew Lang)",
        "year": 1898,
        "source_url": "https://www.gutenberg.org/cache/epub/128/pg128.txt",
        "register": "folk tales"
    },
    # Scientific papers / reports
    {
        "slug": "faraday_candle",
        "title": "The Chemical History of a Candle",
        "author": "Michael Faraday",
        "year": 1861,
        "source_url": "https://www.gutenberg.org/cache/epub/14474/pg14474.txt",
        "register": "scientific lecture"
    },
    {
        "slug": "curie_radioactivity",
        "title": "Radioactive Substances (Nobel Lecture)",
        "author": "Marie Curie",
        "year": 1903,
        "source_url": "https://www.gutenberg.org/cache/epub/7011/pg7011.txt",
        "register": "scientific paper"
    },
    # Poetry
    {
        "slug": "whitman_leaves",
        "title": "Leaves of Grass",
        "author": "Walt Whitman",
        "year": 1855,
        "source_url": "https://www.gutenberg.org/cache/epub/1322/pg1322.txt",
        "register": "poetry"
    },
    {
        "slug": "dickinson_poems",
        "title": "Poems by Emily Dickinson (Series One)",
        "author": "Emily Dickinson",
        "year": 1890,
        "source_url": "https://www.gutenberg.org/cache/epub/12242/pg12242.txt",
        "register": "poetry"
    },
    {
        "slug": "blake_songs",
        "title": "Songs of Innocence and Experience",
        "author": "William Blake",
        "year": 1794,
        "source_url": "https://www.gutenberg.org/cache/epub/1934/pg1934.txt",
        "register": "poetry"
    },
    # Memoir / autobiography
    {
        "slug": "douglass_narrative",
        "title": "Narrative of the Life of Frederick Douglass",
        "author": "Frederick Douglass",
        "year": 1845,
        "source_url": "https://www.gutenberg.org/cache/epub/23/pg23.txt",
        "register": "memoir / autobiography"
    },
    {
        "slug": "tubman_scenes",
        "title": "Scenes in the Life of Harriet Tubman",
        "author": "Kate Clifford Larson (ed.)",
        "year": 1869,
        "source_url": "https://www.gutenberg.org/cache/epub/9999/pg9999.txt",
        "register": "memoir"
    },
    # Travel / geography
    {
        "slug": "polo_travels",
        "title": "The Travels of Marco Polo",
        "author": "Marco Polo",
        "year": 1300,
        "source_url": "https://www.gutenberg.org/cache/epub/10636/pg10636.txt",
        "register": "travel / geography"
    },
    # Medicine / natural philosophy
    {
        "slug": "vesalius_fabrica",
        "title": "The Anatomy of the Human Body (selections)",
        "author": "William Cowper (after Vesalius)",
        "year": 1698,
        "source_url": "https://www.gutenberg.org/cache/epub/17921/pg17921.txt",
        "register": "anatomy / natural philosophy"
    },
    # Ethnography
    {
        "slug": "frazer_golden_bough",
        "title": "The Golden Bough (Abridged)",
        "author": "James George Frazer",
        "year": 1922,
        "source_url": "https://www.gutenberg.org/cache/epub/3623/pg3623.txt",
        "register": "ethnography / anthropology"
    },
]

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "..", "corpus")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "data")

def strip_gutenberg_header_footer(text):
    """
    Remove Project Gutenberg boilerplate from the start and end of a text.
    Looks for the standard START/END markers.
    """
    start_markers = [
        "*** START OF THE PROJECT GUTENBERG",
        "*** START OF THIS PROJECT GUTENBERG",
        "*END*THE SMALL PRINT",
    ]
    end_markers = [
        "*** END OF THE PROJECT GUTENBERG",
        "*** END OF THIS PROJECT GUTENBERG",
        "End of Project Gutenberg",
        "End of the Project Gutenberg",
    ]

    lines = text.split("\n")
    start_idx = 0
    end_idx   = len(lines)

    for i, line in enumerate(lines):
        for marker in start_markers:
            if marker in line.upper():
                start_idx = i + 1
                break

    for i in range(len(lines) - 1, -1, -1):
        for marker in end_markers:
            if marker in lines[i].upper():
                end_idx = i
                break
        else:
            continue
        break

    return "\n".join(lines[start_idx:end_idx]).strip()


def fetch_text(url, slug):
    """Download a text file, strip boilerplate, return cleaned string."""
    print(f"  Fetching {slug} from {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GlassBoxCorpusBot/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        return strip_gutenberg_header_footer(raw)
    except Exception as e:
        print(f"  ERROR fetching {slug}: {e}")
        return None


def main():
    os.makedirs(CORPUS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR,   exist_ok=True)

    index = []
    for entry in CORPUS:
        slug = entry["slug"]
        out_path = os.path.join(CORPUS_DIR, f"{slug}.txt")

        if os.path.exists(out_path):
            print(f"  {slug}.txt already exists, skipping download.")
            char_count = len(open(out_path, encoding="utf-8").read())
        else:
            text = fetch_text(entry["source_url"], slug)
            if text is None:
                print(f"  Skipping {slug} due to fetch error.")
                continue
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(text)
            char_count = len(text)
            time.sleep(1)  # be polite to Gutenberg

        index.append({
            "slug":       slug,
            "title":      entry["title"],
            "author":     entry["author"],
            "year":       entry["year"],
            "register":   entry["register"],
            "source_url": entry["source_url"],
            "file":       f"corpus/{slug}.txt",
            "char_count": char_count,
        })
        print(f"  {slug}: {char_count:,} chars")

    index_path = os.path.join(DATA_DIR, "corpus_index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    print(f"\nCorpus index written to {index_path}")
    print(f"Total texts: {len(index)}")
    total = sum(e["char_count"] for e in index)
    print(f"Total corpus size: {total:,} chars (~{total/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
