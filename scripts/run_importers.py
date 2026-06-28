#!/usr/bin/env python3
"""run_importers.py

Iterate over the queries in the query/ folder in alphanumerical order,
dispatch each to its respective modular importer, and write the combined
results into wiki/intermediate_tiddlers.json.
"""

import os
import sys
import json
from pathlib import Path

# Add the project root to sys.path to allow imports from scripts.importers
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.importers import sparql, json_source, rss

QUERY_DIR = Path(os.environ.get("WIKITIDDLER_QUERY_DIR", "query"))
WIKI_DIR = Path(os.environ.get("WIKITIDDLER_WIKI_DIR", "wiki"))
INTERMEDIATE_FILE = WIKI_DIR / "intermediate_tiddlers.json"

def main():
    if not QUERY_DIR.exists():
        print(f"Error: query directory not found: {QUERY_DIR}", file=sys.stderr)
        sys.exit(1)

    query_files = sorted(QUERY_DIR.glob("*.*"))
    if not query_files:
        print(f"No queries found in {QUERY_DIR}")
        sys.exit(0)

    all_tiddlers = []

    for query_file in query_files:
        ext = query_file.suffix.lower()
        print(f"Processing {query_file.name}...")
        
        tiddlers = []
        try:
            if ext == ".sparql":
                tiddlers = sparql.process(query_file)
            elif ext == ".json":
                tiddlers = json_source.process(query_file)
            elif ext == ".rss":
                tiddlers = rss.process(query_file)
            else:
                print(f"Skipping {query_file.name}: Unknown extension '{ext}'.")
                continue
                
            print(f"  -> Generated {len(tiddlers)} tiddler(s).")
            all_tiddlers.extend(tiddlers)
        except Exception as e:
            print(f"Error processing {query_file.name}: {e}", file=sys.stderr)
            # You may choose to sys.exit(1) here depending on strictness
            sys.exit(1)

    WIKI_DIR.mkdir(parents=True, exist_ok=True)
    with open(INTERMEDIATE_FILE, "w", encoding="utf-8") as f:
        json.dump(all_tiddlers, f, indent=2, ensure_ascii=False)
        
    print(f"Total: Wrote {len(all_tiddlers)} intermediate tiddlers to {INTERMEDIATE_FILE}.")

if __name__ == "__main__":
    main()
