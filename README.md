# wikitiddler

A GitHub Action that extracts data from multiple sources (Wikidata SPARQL, JSON endpoints, RSS feeds), converts the results to TiddlyWiki tiddlers with Python, builds a single-file TiddlyWiki with Node.js, and deploys it to GitHub Pages — on a monthly schedule or on demand.

## How it works

```
query/
├── 01_query.sparql
├── 02_news.rss
└── 03_data.json
      │  (Multiple sources fetched by modular importers)
      ▼
scripts/run_importers.py
      │  (Standardized intermediate JSON)
      ▼
scripts/json_to_tiddlers.py   ←   templates/*.tid
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
queries and templates.

> **Note:** You will not automatically receive updates to the pipeline
> (Python scripts, workflow logic) if this repository improves.  Use
> Option B if that matters to you.

### Option B — Reference the action (recommended for staying up to date)

Create a minimal repository yourself.  The only files you need are your
query configurations, your template tiddlers, and a workflow that calls this action.
When this repository is updated, your next build automatically picks up the
improvements — no changes to your repo required.

**Minimal repository layout:**

```
my-wiki/
├── query/
│   ├── 01_query.sparql        ← your queries
│   └── 02_news.rss
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
      - uses: andjar/wikitiddler@v1
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

## Multiple Queries and Importers

Wikitiddler processes files in the `query/` folder in **alphanumerical order**. 
The extension of the file determines which importer is used. 

Available importers:
- **`.sparql`**: Queries Wikidata.
- **`.json`**: Fetches a JSON URL or local file, uses JMESPath to extract items.
- **`.rss`**: Fetches an RSS or Atom feed, uses JMESPath to extract items.

### 1. SPARQL Importer (`*.sparql`)

The query **must** include a column named `?item` containing full Wikidata
entity URIs.

```sparql
SELECT ?item ?itemLabel …
WHERE {
  ?item wdt:P31 wd:Q5 .   # your filter here
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
```

- Multi-valued properties must use `GROUP_CONCAT(DISTINCT ?val; SEPARATOR="|")`.
- If a `?description` column is present, it becomes the tiddler **body**.
- `xsd:dateTime` and `xsd:date` are automatically converted to TiddlyWiki format.

### 2. JSON and RSS Importers (`*.json`, `*.rss`)

These files use YAML configuration to define the source URL and field mapping using JMESPath. 
Even though the extensions are `.json` or `.rss`, the content format is **YAML**.

Example `query/02_news.rss`:
```yaml
url: "https://news.ycombinator.com/rss"
items_path: "entries"
mapping:
  title: "link"
  text: "summary"
  article_title: "title"
  link: "link"
  tags: "'[[NewsItem]]'"
```

Example `query/03_data.json` demonstrating how to flatten nested properties:
```yaml
url: "https://dummyjson.com/users"
items_path: "users"
mapping:
  title: "username"
  text: "userAgent"
  full_name: "join(' ', [firstName, lastName])"
  company_name: "company.name"
  company_department: "company.department"
  address_city: "address.city"
  tags: "'[[User]] [[JSONData]]'"
```

- `url`: The endpoint to fetch.
- `items_path`: JMESPath to the array of items. For RSS/feedparser, this is usually `"entries"`. For JSON, it might be `"data.results"` or `"@"` (root list).
- `mapping`: JMESPath queries relative to each item to generate TiddlyWiki fields. 
  - The `title` mapping is **required** (to uniquely identify the tiddler).
  - The `text` mapping generates the tiddler body.
  - Constant strings can be passed in quotes (e.g. `"'NewsItem'"`).

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

## Action inputs

All inputs are optional.

| Input | Default | Description |
|-------|---------|-------------|
| `query-dir` | `query` | Directory containing the query configuration files |
| `templates-dir` | `templates` | Directory of `.tid` template tiddlers |
| `wiki-dir` | `wiki` | TiddlyWiki wiki directory (`tiddlywiki.info` location) |
| `output-dir` | `dist` | Build output directory for `index.html` |

## Adding TiddlyWiki templates

Place any `.tid` file in `templates/`.  These files are copied verbatim into
the wiki at build time and can define:

- **View templates** to control how item tiddlers render
- **Stylesheets** (`$:/tags/Stylesheet`)
- **Macros**, **filters**, navigation tiddlers, etc.

---

## Local development

```bash
# Install dependencies
pip install -r requirements.txt
npm install           # Windows: cmd /c npm install

# Run the pipeline
python scripts/run_importers.py
python scripts/json_to_tiddlers.py
npx tiddlywiki wiki --output dist --build index

# Open dist/index.html in a browser
```

---

## Versioning

When referencing this action from your own repo, pin to a release tag rather
than `@main` to avoid unexpected breaking changes:

```yaml
- uses: andjar/wikitiddler@v1   # stable
# vs.
- uses: andjar/wikitiddler@main # always latest — may break
```
