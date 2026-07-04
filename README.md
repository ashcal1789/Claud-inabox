# The Glass-Box Language Machine

A small, fully transparent generative text system and public website. It generates new sentences by recombining fragments from a curated public-domain library. 

The defining feature of this project is **provenance**: every generated sentence is fully traceable. You can click any sentence on the site to see exactly which source files, and which character spans within those files, contributed each fragment.

There are no neural networks or LLMs involved in the generation itself. The engine is a deterministic, fully inspectable Python script. It is a language machine with receipts.

## Architecture

The project consists of three parts:

1. **The Corpus (`/corpus/`)**: A curated library of 24 public-domain texts (totaling ~10MB) sourced from Project Gutenberg. It spans natural history, philosophy, trial transcripts, ship logs, poetry, and personal letters.
2. **The Engine (`/engine/`)**: A Python script that selects fragments from the corpus and recombines them into new sentences using a simple bigram/POS bridge. It meticulously records the character offsets of every fragment it borrows.
3. **The Site (`/site/`)**: A static, vanilla HTML/CSS/JS frontend that displays the daily generations and renders the interactive provenance panels.

## Automated Provenance Verification

Because provenance is the core guarantee of the project, it is programmatically verified. The script `engine/verify_provenance.py` runs against every generation file and asserts that:
- The recorded character offsets are valid.
- Slicing the source text file at those offsets yields the exact fragment string recorded in the JSON, byte-for-byte.
- No two fragments in a single sentence come from the same source text.

A `verification_report.json` is generated and committed alongside every run.

## Raw Data Access

The site is fully open to AI agents, crawlers, and researchers. Alongside the HTML, the raw data is served statically at:
- `data/corpus_index.json`
- `data/generation_index.json`
- `data/generations/{run_id}.json`

## Running Locally

To run the engine and view the site locally:

1. Clone the repository.
2. Generate a new batch of sentences:
   ```bash
   python3 engine/generate.py --count 20
   ```
3. Verify the provenance:
   ```bash
   python3 engine/verify_provenance.py
   ```
4. Build the site index:
   ```bash
   python3 engine/build_index.py
   ```
5. Serve the site locally:
   ```bash
   cd site
   python3 -m http.server 8000
   ```
   Then open `http://localhost:8000` in your browser.

## Deployment (GitHub Pages)

The project is designed to run autonomously via GitHub Actions.

1. Push the repository to GitHub.
2. Go to your repository **Settings** -> **Pages**.
3. Under "Build and deployment", set the source to **GitHub Actions**.
4. The workflow in `.github/workflows/generate.yml` will automatically run daily at midnight UTC. It will:
   - Run the generation engine.
   - Run the verification suite (and fail the build if provenance is broken).
   - Commit the new JSON data back to the `main` branch.
   - Deploy the updated site to GitHub Pages.

**Note on permissions:** For the Actions workflow to commit data back to the repo, you must ensure that GitHub Actions has write access. Go to **Settings** -> **Actions** -> **General** -> **Workflow permissions** and select "Read and write permissions".

## Modifying the Corpus

To add or remove texts:
1. Add/remove the `.txt` files in `/corpus/`.
2. Update the metadata in `data/corpus_index.json`.
3. If you want to use the automated fetcher, modify the `CORPUS` list in `engine/fetch_corpus.py` and run it.

## Repository

[https://github.com/ashcal1789/Claud-inabox](https://github.com/ashcal1789/Claud-inabox)

## License

MIT License. See `LICENSE` for details. All corpus texts are public domain.
