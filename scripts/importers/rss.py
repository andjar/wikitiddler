import yaml
import feedparser
import jmespath
import json
from pathlib import Path

def process(file_path: Path) -> list[dict]:
    """Process an RSS/Atom configuration file to extract items and map to tiddlers."""
    config = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    
    url = config.get("url")
    if not url:
        print(f"Skipping {file_path.name}: No URL provided.")
        return []
        
    print(f"Fetching RSS/Atom feed from {url} for {file_path.name}…")
    feed = feedparser.parse(url)
    
    # We serialize feed to a basic dict so jmespath can query it easily.
    # Feedparser objects are dict-like, but full conversion ensures compatibility.
    # json serialization/deserialization is a quick trick to strip custom objects.
    # (Since feedparser uses some custom types like time.struct_time, default=str handles them).
    feed_dict = json.loads(json.dumps(feed, default=str))

    items_path = config.get("items_path", "entries")
    items = jmespath.search(items_path, feed_dict)
    
    if not items or not isinstance(items, list):
        print(f"Warning: {items_path} did not return a list of entries.")
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
        
        if "title" not in tiddler:
            print(f"Warning: RSS item skipped because mapping produced no 'title' field.")
            continue
            
        tiddlers.append(tiddler)
        
    return tiddlers
