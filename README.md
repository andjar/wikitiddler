# wikitiddler

A GitHub Action that queries Wikidata via SPARQL, converts the results to
TiddlyWiki tiddlers with Python, builds a single-file TiddlyWiki with Node.js,
and deploys it to GitHub Pages — on a monthly schedule or on demand.

## How it works

```
query/query.sparql
      │  (SPARQL → Wikidata endpoint)
      ▼
scripts/sparql_to_tiddlers.py   ←   templates/*.tid
      │  (one .tid file per item)
      ▼
wiki/tiddlers/
      │
      ▼
tiddlywiki wiki --build index
      │
      ▼
dist/index.html  →  GitHub Pages
```

---

## Two ways to use this

### Option A — GitHub template (quickest start)

Click **"Use this template"** at the top of this repository to create your
own copy with a clean git history.  You get all the files; just edit the
query and templates.

> **Note:** You will not automatically receive updates to the pipeline
> (Python script, workflow logic) if this repository improves.  Use
> Option B if that matters to you.

### Option B — Reference the action (recommended for staying up to date)

Create a minimal repository yourself.  The only files you need are your
SPARQL query, your template tiddlers, and a workflow that calls this action.
When this repository is updated, your next build automatically picks up the
improvements — no changes to your repo required.

**Minimal repository layout:**

```
my-wiki/
├── query/
│   └── query.sparql           ← your SPARQL query
├── templates/                 ← your TiddlyWiki .tid files (optional)
│   └── *.tid
└── .github/
    └── workflows/
        └── build.yml          ← copy the snippet below
```

**`.github/workflows/build.yml`** for your repo:

```yaml
name: Build and Deploy Wiki

on:
  workflow_dispatch:
  schedule:
    - cron: '0 3 1 * *'   # monthly, 1st of month at 03:00 UTC

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: OWNER/wikitiddler@v1   # replace OWNER with this repo's owner
        id: wiki
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ${{ steps.wiki.outputs.output-dir }}/

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/deploy-pages@v4
        id: deployment
```

No `package.json`, `requirements.txt`, or `scripts/` directory needed in
your repo — the action provides everything.

---

## First-time GitHub Pages setup

In your repository **Settings → Pages → Source**, select **GitHub Actions**.
Then go to **Actions → Build and Deploy Wiki → Run workflow** to build and
publish your wiki for the first time.  It will be available at
`https://<you>.github.io/<repo>/`.

---

## Triggering a build

| Method | How |
|--------|-----|
| Manual | Actions tab → *Build and Deploy Wiki* → **Run workflow** |
| Scheduled | Automatically on the 1st of every month at 03:00 UTC |

To change the schedule, edit the `cron` value in your workflow file:

```yaml
schedule:
  - cron: '0 3 1 * *'   # min hour day-of-month month weekday
```

---

## Action inputs

All inputs are optional.

| Input | Default | Description |
|-------|---------|-------------|
| `query-file` | `query/query.sparql` | Path to the SPARQL query file |
| `templates-dir` | `templates` | Directory of `.tid` template tiddlers |
| `wiki-dir` | `wiki` | TiddlyWiki wiki directory (`tiddlywiki.info` location) |
| `output-dir` | `dist` | Build output directory for `index.html` |

Example — using non-default paths:

```yaml
- uses: OWNER/wikitiddler@v1
  id: wiki
  with:
    query-file: src/my-query.sparql
    templates-dir: src/templates
```

## Action outputs

| Output | Description |
|--------|-------------|
| `output-dir` | Directory containing the built `index.html` |

---

## Customising `tiddlywiki.info`

By default the action installs a minimal `tiddlywiki.info` into `wiki/` if one
does not already exist.  To customise it (add plugins, themes, a description),
create `wiki/tiddlywiki.info` in your repository:

```json
{
  "description": "My Wikidata wiki",
  "plugins": ["tiddlywiki/codemirror"],
  "themes": ["tiddlywiki/vanilla"],
  "build": {
    "index": [
      "--rendertiddler",
      "$:/core/save/all",
      "index.html",
      "text/plain"
    ]
  }
}
```

---

## Writing the SPARQL query

Edit `query/query.sparql`.  The Nobel Prize laureates query in this
repository is a working example to replace.

### Required convention

The query **must** include a column named `?item` containing full Wikidata
entity URIs:

```sparql
SELECT ?item ?itemLabel …
WHERE {
  ?item wdt:P31 wd:Q5 .   # your filter here
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
```

### Multi-valued properties

Multi-valued properties must be aggregated in the query using `GROUP_CONCAT`
with a pipe separator.  The action automatically converts the result to
TiddlyWiki list format (`[[val1]] [[val2]] …`), so your templates can use
`[list[currentTiddler!!occupations]]` directly.

For human-readable labels in `GROUP_CONCAT`, use explicit `rdfs:label` lookups
rather than relying on `SERVICE wikibase:label` — the label service does not
reliably populate label variables inside aggregates:

```sparql
SELECT
  ?item
  ?itemLabel
  (GROUP_CONCAT(DISTINCT ?occupationLabel; SEPARATOR="|") AS ?occupations)
WHERE {
  ?item wdt:P31 wd:Q5 .
  OPTIONAL {
    ?item wdt:P106 ?occupationItem .
    ?occupationItem rdfs:label ?occupationLabel .
    FILTER(LANG(?occupationLabel) = "en")
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
GROUP BY ?item ?itemLabel
```

`SERVICE wikibase:label` is still used for `?itemLabel` and `?itemDescription`
on the main item.

### Automatic value conversions

The Python script applies two conversions automatically:

| Input (from Wikidata) | Stored in tiddler |
|-----------------------|-------------------|
| `xsd:dateTime` / `xsd:date` literal, e.g. `1941-05-24T00:00:00Z` | TiddlyWiki datetime: `19410524000000000` |
| Pipe-separated GROUP_CONCAT value, e.g. `novelist\|poet` | TiddlyWiki list: `[[novelist]] [[poet]]` |

### Tiddler body

If the query includes a `?description` column its value becomes the tiddler
**body** (free text) rather than a named field.

### Field names

SPARQL variable names are lowercased and sanitised to produce valid TiddlyWiki
field names:

| SPARQL variable | Tiddler field |
|-----------------|---------------|
| `?itemLabel` | `itemlabel` |
| `?birthdate` | `birthdate` |
| `?occupations` | `occupations` |

---

## Adding TiddlyWiki templates

Place any `.tid` file in `templates/`.  These files are copied verbatim into
the wiki at build time and can define:

- **View templates** to control how item tiddlers render
- **Stylesheets** (`$:/tags/Stylesheet`)
- **Macros**, **filters**, navigation tiddlers, etc.

Example template — rendering a multi-valued field as a linked list:

```
title: $:/templates/WikidataItemView
tags: $:/tags/ViewTemplate
list-before: $:/core/ui/ViewTemplate/body

Occupations:
<$list filter="[list[!!occupations]]">
  <$link><$text text=<<currentTiddler>>/></$link>
</$list>
```

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt
npm install           # Windows: cmd /c npm install

# Run the pipeline
python scripts/sparql_to_tiddlers.py
npx tiddlywiki wiki --output dist --build index

# Open dist/index.html in a browser
```

---

## Versioning

When referencing this action from your own repo, pin to a release tag rather
than `@main` to avoid unexpected breaking changes:

```yaml
- uses: OWNER/wikitiddler@v1   # stable
# vs.
- uses: OWNER/wikitiddler@main # always latest — may break
```

Create a release tag in this repository (**Releases → Draft a new release**)
whenever the pipeline logic changes in a backwards-compatible way, and bump
the major version for breaking changes.
