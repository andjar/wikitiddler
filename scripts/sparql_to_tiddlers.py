#!/usr/bin/env python3
"""sparql_to_tiddlers.py

Read a SPARQL query from query/query.sparql, execute it against the Wikidata
endpoint, and convert each result row into a TiddlyWiki .tid file written to
wiki/tiddlers/.

SPARQL conventions
------------------
- ?item        : required — Wikidata entity URI (e.g. http://www.wikidata.org/entity/Q42)
- ?itemLabel   : recommended — human-readable label (via SERVICE wikibase:label)
- multi-valued columns should use GROUP_CONCAT(DISTINCT ?x; SEPARATOR="|") in the query
- datetime columns (xsd:dateTime / xsd:date) are auto-converted to TiddlyWiki format

Tiddler output
--------------
One .tid file per item, named <QID>.tid.  All SPARQL columns become tiddler
fields (variable name lowercased).  If a ?description column is present its
value becomes the tiddler body.

Value conversions applied automatically:
- xsd:dateTime / xsd:date  →  YYYYMMDDhhmmssSSS  (TiddlyWiki datetime format)
- pipe-separated lists      →  [[val1]] [[val2]]  (TiddlyWiki list format)

Template tiddlers in templates/ are copied verbatim into wiki/tiddlers/ so
that TiddlyWiki picks them up in the build.
"""

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Paths (relative to the repository root; run from there)
# ---------------------------------------------------------------------------
QUERY_FILE = Path("query/query.sparql")
OUTPUT_DIR = Path("wiki/tiddlers")
TEMPLATES_DIR = Path("templates")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "wikitiddler/1.0 (https://github.com/wikitiddler)"

# ---------------------------------------------------------------------------
# Wikidata helpers
# ---------------------------------------------------------------------------

def query_wikidata(sparql: str) -> dict:
    """POST a SPARQL query and return the parsed JSON response."""
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/sparql-results+json",
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


_XSD_DATETIME = "http://www.w3.org/2001/XMLSchema#dateTime"
_XSD_DATE = "http://www.w3.org/2001/XMLSchema#date"
_XSD_GYEAR = "http://www.w3.org/2001/XMLSchema#gYear"
_DATETIME_DATATYPES = {_XSD_DATETIME, _XSD_DATE, _XSD_GYEAR}


def _to_tw_datetime(value: str) -> str:
    """Convert a Wikidata ISO date/datetime string to TiddlyWiki YYYYMMDDhhmmssSSS.

    Handles the common Wikidata patterns:
      1941-05-24T00:00:00Z  →  19410524000000000
      1941-05-24            →  19410524000000000
      1900                  →  19000101000000000  (gYear)
    Wikidata zero-month / zero-day precision dates (e.g. 1900-00-00) have the
    unknown parts replaced with 01 before parsing.
    BCE dates (negative year) are returned unchanged.
    """
    raw = value.lstrip("+").rstrip("Z")
    if raw.startswith("-"):
        return value  # BCE — no suitable TW representation

    # Replace Wikidata's zero-month / zero-day placeholders with 01
    raw = re.sub(r"-00(?=-|T|$)", "-01", raw)

    try:
        if "T" in raw:
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
        elif len(raw) == 10:
            dt = datetime.strptime(raw, "%Y-%m-%d")
        elif len(raw) == 4:  # gYear
            dt = datetime.strptime(raw, "%Y")
        else:
            return value
        return dt.strftime("%Y%m%d%H%M%S") + "000"
    except ValueError:
        return value


def _to_tw_list(value: str) -> str:
    """Convert a pipe-separated GROUP_CONCAT value to TiddlyWiki list format.

    "United States|Germany"  →  "[[United States]] [[Germany]]"
    Single-value strings are also wrapped for consistency.
    """
    parts = [p.strip() for p in value.split("|") if p.strip()]
    return " ".join(f"[[{p}]]" for p in parts)


def process_binding(binding: dict) -> str:
    """Extract and format a SPARQL result binding value for TiddlyWiki.

    Applies in order:
    1. URI  →  local name (Q-ID / P-ID)
    2. xsd:dateTime / xsd:date / xsd:gYear  →  TiddlyWiki datetime
    3. Pipe-separated literal  →  TiddlyWiki [[val1]] [[val2]] list
    4. Plain literal  →  as-is
    """
    value = binding.get("value", "")
    btype = binding.get("type", "")
    datatype = binding.get("datatype", "")

    if btype == "uri":
        return value.rsplit("/", 1)[-1]

    if datatype in _DATETIME_DATATYPES:
        return _to_tw_datetime(value)

    if "|" in value:
        return _to_tw_list(value)

    return value


# ---------------------------------------------------------------------------
# Tiddler helpers
# ---------------------------------------------------------------------------

def sanitize_field_name(name: str) -> str:
    """Convert a SPARQL variable name to a valid TiddlyWiki field name.

    TiddlyWiki field names are lowercase; only letters, digits, hyphens and
    underscores are safe.  Any other character is replaced with a hyphen.
    """
    name = name.lower()
    name = re.sub(r"[^a-z0-9_-]", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name


def row_to_tid(row: dict) -> tuple[str | None, str | None]:
    """Convert one SPARQL result row to a (qid, tid_content) pair.

    Returns (None, None) if the row lacks a valid ?item binding.
    The tiddler body is set from ?description when present; all other
    variables become named fields.
    """
    item_binding = row.get("item")
    if not item_binding:
        return None, None

    qid = process_binding(item_binding)
    if not qid.startswith("Q"):
        return None, None

    fields: dict[str, str] = {
        "title": qid,
        "tags": "WikidataItem",
    }
    body = ""

    for var, binding in row.items():
        if var == "item":
            continue
        field_name = sanitize_field_name(var)
        value = process_binding(binding)
        if not value:
            continue
        if field_name == "description":
            body = value
        else:
            fields[field_name] = value

    lines = [f"{k}: {v}" for k, v in fields.items()]
    # TiddlyWeb .tid format: metadata lines, blank line, optional body
    tid_content = "\n".join(lines) + "\n\n" + body + "\n"
    return qid, tid_content


def clear_generated_tiddlers(output_dir: Path) -> None:
    """Remove previously generated *.tid files so stale items do not persist."""
    removed = 0
    for f in output_dir.glob("*.tid"):
        f.unlink()
        removed += 1
    if removed:
        print(f"Removed {removed} stale tiddler(s) from {output_dir}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not QUERY_FILE.exists():
        print(f"Error: query file not found: {QUERY_FILE}", file=sys.stderr)
        sys.exit(1)

    sparql = QUERY_FILE.read_text(encoding="utf-8")

    print(f"Querying Wikidata SPARQL endpoint…")
    try:
        data = query_wikidata(sparql)
    except requests.HTTPError as exc:
        print(f"SPARQL request failed: {exc}", file=sys.stderr)
        sys.exit(1)
    except requests.Timeout:
        print("SPARQL request timed out (>120 s).", file=sys.stderr)
        sys.exit(1)

    rows = data["results"]["bindings"]
    print(f"Received {len(rows)} row(s) from endpoint.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clear_generated_tiddlers(OUTPUT_DIR)

    written = 0
    skipped = 0
    for row in rows:
        qid, content = row_to_tid(row)
        if qid is None:
            skipped += 1
            continue
        (OUTPUT_DIR / f"{qid}.tid").write_text(content, encoding="utf-8")
        written += 1

    print(f"Wrote {written} tiddler(s) to {OUTPUT_DIR}/  ({skipped} row(s) skipped).")

    # Copy template tiddlers into the wiki tiddlers directory
    if TEMPLATES_DIR.exists():
        copied = 0
        for tid_file in TEMPLATES_DIR.rglob("*.tid"):
            dest = OUTPUT_DIR / tid_file.name
            shutil.copy(tid_file, dest)
            copied += 1
        if copied:
            print(f"Copied {copied} template tiddler(s) from {TEMPLATES_DIR}/.")
        else:
            print(f"No .tid files found in {TEMPLATES_DIR}/.")
    else:
        print(f"No templates/ directory found — skipping template copy.")


if __name__ == "__main__":
    main()
