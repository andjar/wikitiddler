#!/usr/bin/env python3
"""json_to_tiddlers.py

Read intermediate_tiddlers.json and convert each object into a TiddlyWiki .tid file
written to wiki/tiddlers/. Also handles copying template tiddlers and clearing
stale generated tiddlers.
"""

import os
import sys
import json
import shutil
import re
from pathlib import Path

WIKI_DIR = Path(os.environ.get("WIKITIDDLER_WIKI_DIR", "wiki"))
INTERMEDIATE_FILE = WIKI_DIR / "intermediate_tiddlers.json"
OUTPUT_DIR = WIKI_DIR / "tiddlers"
TEMPLATES_DIR = Path(os.environ.get("WIKITIDDLER_TEMPLATES_DIR", "templates"))

def sanitize_filename(name: str) -> str:
    """Convert a tiddler title into a valid filesystem filename."""
    # This matches TiddlyWiki's basic filesystem sanitization logic
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name

def clear_generated_tiddlers(output_dir: Path) -> None:
    """Remove previously generated *.tid files so stale items do not persist."""
    removed = 0
    for f in output_dir.glob("*.tid"):
        f.unlink()
        removed += 1
    if removed:
        print(f"Removed {removed} stale tiddler(s) from {output_dir}/")

def dict_to_tid(tiddler: dict) -> tuple[str, str]:
    """Convert a dictionary to a (filename, tid_content) pair.
    
    The 'text' key becomes the tiddler body. All other keys become fields.
    """
    if "title" not in tiddler:
        raise ValueError("Tiddler dictionary must contain a 'title' field.")
        
    title = tiddler["title"]
    filename = sanitize_filename(title)
    
    body = tiddler.pop("text", "")
    
    # Ensure title is at the top of the metadata
    fields = {"title": title}
    for k, v in tiddler.items():
        if k != "title":
            # Sanitize field name: TiddlyWiki requires lowercase, basic chars
            field_name = k.lower()
            field_name = re.sub(r"[^a-z0-9_-]", "-", field_name)
            field_name = re.sub(r"-{2,}", "-", field_name).strip("-")
            
            # Avoid empty field names
            if not field_name:
                continue
                
            fields[field_name] = v
            
    lines = [f"{k}: {v}" for k, v in fields.items()]
    tid_content = "\n".join(lines) + "\n\n" + body + "\n"
    
    return filename, tid_content

def main():
    if not INTERMEDIATE_FILE.exists():
        print(f"Error: intermediate file not found: {INTERMEDIATE_FILE}", file=sys.stderr)
        sys.exit(1)

    with open(INTERMEDIATE_FILE, "r", encoding="utf-8") as f:
        tiddlers = json.load(f)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clear_generated_tiddlers(OUTPUT_DIR)

    written = 0
    for idx, tiddler in enumerate(tiddlers):
        try:
            filename, content = dict_to_tid(tiddler)
            # Ensure unique filenames if there are title collisions
            out_file = OUTPUT_DIR / f"{filename}.tid"
            suffix_counter = 1
            while out_file.exists():
                out_file = OUTPUT_DIR / f"{filename}_{suffix_counter}.tid"
                suffix_counter += 1
                
            out_file.write_text(content, encoding="utf-8")
            written += 1
        except Exception as e:
            print(f"Error processing tiddler at index {idx}: {e}", file=sys.stderr)

    print(f"Wrote {written} tiddler(s) to {OUTPUT_DIR}/")

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

    # Remove the intermediate file to clean up
    INTERMEDIATE_FILE.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
