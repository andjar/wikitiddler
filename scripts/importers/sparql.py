import re
import requests
from datetime import datetime
from pathlib import Path

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "wikitiddler/1.0 (https://github.com/wikitiddler)"

_XSD_DATETIME = "http://www.w3.org/2001/XMLSchema#dateTime"
_XSD_DATE = "http://www.w3.org/2001/XMLSchema#date"
_XSD_GYEAR = "http://www.w3.org/2001/XMLSchema#gYear"
_DATETIME_DATATYPES = {_XSD_DATETIME, _XSD_DATE, _XSD_GYEAR}

def _to_tw_datetime(value: str) -> str:
    raw = value.lstrip("+").rstrip("Z")
    if raw.startswith("-"):
        return value

    raw = re.sub(r"-00(?=-|T|$)", "-01", raw)

    try:
        if "T" in raw:
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
        elif len(raw) == 10:
            dt = datetime.strptime(raw, "%Y-%m-%d")
        elif len(raw) == 4:
            dt = datetime.strptime(raw, "%Y")
        else:
            return value
        return dt.strftime("%Y%m%d%H%M%S") + "000"
    except ValueError:
        return value

def _to_tw_list(value: str) -> str:
    parts = [p.strip() for p in value.split("|") if p.strip()]
    return " ".join(f"[[{p}]]" for p in parts)

def process_binding(binding: dict) -> str:
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

def sanitize_field_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9_-]", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    return name

def process(file_path: Path) -> list[dict]:
    """Execute SPARQL query and return a list of intermediate tiddler dicts."""
    sparql = file_path.read_text(encoding="utf-8")

    print(f"Querying Wikidata SPARQL endpoint for {file_path.name}…")
    resp = requests.get(
        SPARQL_ENDPOINT,
        params={"query": sparql, "format": "json"},
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    rows = data["results"]["bindings"]
    tiddlers = []
    
    for row in rows:
        item_binding = row.get("item")
        if not item_binding:
            continue

        qid = process_binding(item_binding)
        if not qid.startswith("Q"):
            continue

        tiddler = {
            "title": qid,
            "tags": "[[WikidataItem]]",
        }
        
        for var, binding in row.items():
            if var == "item":
                continue
            field_name = sanitize_field_name(var)
            value = process_binding(binding)
            if not value:
                continue
            if field_name == "description":
                tiddler["text"] = value
            else:
                tiddler[field_name] = value

        tiddlers.append(tiddler)

    return tiddlers
