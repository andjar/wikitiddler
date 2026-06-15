# wikitiddler

A GitHub Actions pipeline that queries Wikidata via SPARQL, converts the
results to TiddlyWiki tiddlers with Python, builds a single-file TiddlyWiki
with Node.js, and deploys it to GitHub Pages — automatically on a monthly
schedule or on demand.

## How it works

```
query/query.sparql
        │
        ▼
scripts/sparql_to_tiddlers.py   ←   templates/*.tid
        │ (writes .tid files)
        ▼
wiki/tiddlers/
        │
        ▼
tiddlywiki wiki --build index
        │
        ▼
dist/index.html  →  GitHub Pages
```

1. The Python script reads `query/query.sparql` and sends it to the Wikidata
   SPARQL endpoint.
2. Each row in the result becomes one `.tid` file (one tiddler per Wikidata
   item) written to `wiki/tiddlers/`.
3. Template tiddlers from `templates/` are copied into `wiki/tiddlers/` so
   that the TiddlyWiki build picks them up.
4. TiddlyWiki Node.js assembles everything in `wiki/` into a single
   `dist/index.html`.
5. GitHub Actions deploys `dist/` to GitHub Pages.

## Repository layout

```
wikitiddler/
├── .github/workflows/build.yml   GitHub Actions workflow
├── query/query.sparql            SPARQL query — edit this
├── templates/                    TiddlyWiki UI/rendering tiddlers — edit these
│   └── *.tid
├── wiki/
│   ├── tiddlywiki.info           TiddlyWiki configuration
│   └── tiddlers/                 Assembled at build time (gitignored *.tid)
├── scripts/sparql_to_tiddlers.py Python conversion script
├── requirements.txt              Python dependencies
└── package.json                  Node.js dependencies
```

## First-time GitHub setup

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

### 2. Enable GitHub Pages

In the repository **Settings → Pages → Source**, select **GitHub Actions**.
No branch configuration is needed — the workflow handles deployment directly.

### 3. Run the workflow

Go to **Actions → Build and Deploy Wiki → Run workflow**.  The wiki will be
available at `https://<you>.github.io/<repo>/` once the run completes.

## Triggering a build

| Method | How |
|--------|-----|
| Manual | Actions tab → *Build and Deploy Wiki* → **Run workflow** |
| Scheduled | Runs automatically on the 1st of every month at 03:00 UTC |

To change the schedule, edit the `cron` value in
`.github/workflows/build.yml`:

```yaml
schedule:
  - cron: '0 3 1 * *'   # min hour day month weekday
```

## Customising the SPARQL query

Edit `query/query.sparql`.  Replace the example (Nobel Literature laureates)
with any query that returns Wikidata items.

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
with a pipe separator.  The Python script automatically converts the result to
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

The Python script applies two conversions automatically — no query changes needed:

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
| `?itemLabel`    | `itemlabel`   |
| `?birthdate`    | `birthdate`   |
| `?occupations`  | `occupations` |

## Adding TiddlyWiki templates

Place any `.tid` file in `templates/`.  These files are copied verbatim into
the wiki at build time and can define:

- **View templates** (`$:/view-template`) to control how item tiddlers render
- **Stylesheets** (`$:/tags/Stylesheet`)
- **Macros**, **filters**, navigation tiddlers, etc.

Example template — rendering a multi-valued field as a list:

```
title: $:/templates/WikidataItemView
tags: $:/tags/ViewTemplate
list-before: $:/core/ui/ViewTemplate/body

\define renderField(name)
<$list filter="[{!!$name$}split[|]]">
  <$link to={{!!title}}><<currentTiddler>></$link>
</$list>
\end

Occupations: <<renderField "occupations">>
```

## Local development

```bash
# Install dependencies
pip install -r requirements.txt
npm install           # or: cmd /c npm install  (Windows)

# Run the pipeline locally
python scripts/sparql_to_tiddlers.py
npx tiddlywiki wiki --output dist --build index

# Open dist/index.html in a browser
```
