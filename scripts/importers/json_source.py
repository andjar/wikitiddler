import json
import yaml
import requests
import jmespath
from pathlib import Path

def process(file_path: Path) -> list[dict]:
    """Process a JSON configuration file to extract items and map to tiddlers."""
    config = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    
    url = config.get("url")
    if not url:
        print(f"Skipping {file_path.name}: No URL provided.")
        return []
        
    print(f"Fetching JSON from {url} for {file_path.name}…")
    if url.startswith("http://") or url.startswith("https://"):
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    else:
        with open(url, "r", encoding="utf-8") as f:
            data = json.load(f)

    items_path = config.get("items_path", "@")
    items = jmespath.search(items_path, data)
    
    if not items or not isinstance(items, list):
        print(f"Warning: {items_path} did not return a list of items.")
        return []

    mapping = config.get("mapping", {})
    tiddlers = []
    
    for item in items:
        tiddler = {}
        for tw_field, jmes_expr in mapping.items():
            val = jmespath.search(jmes_expr, item)
            if val is not None:
                if isinstance(val, (list, dict)):
                    tiddler[tw_field] = json.dumps(val)
                else:
                    tiddler[tw_field] = str(val)
        
        # Ensure there is a title
        if "title" not in tiddler:
            print(f"Warning: item skipped because mapping produced no 'title' field.")
            continue
            
        tiddlers.append(tiddler)
        
    return tiddlers
