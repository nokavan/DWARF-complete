#!/usr/bin/env python3
"""
Builds tools/wh3_api_names.json from CA's official scripting documentation, which ships inside the
game's data.pack (documentation/script/...). Only NAMES are stored (functions, events, methods).

  python3 tools/extract_api.py DATA_PACK
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from game_data import Pack  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    p = Pack(sys.argv[1])
    docs = {}
    for e in p.entries:
        if e[0].startswith("documentation/script/") and e[0].endswith(".html"):
            t = html.unescape(p.read(e).decode("utf-8", "replace"))
            docs[e[0][len("documentation/script/"):]] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))

    def get(*names):
        return " ".join(docs.get(n, "") for n in names)

    cm_doc = get("campaign/campaign_manager.html", "campaign/episodic_scripting.html")
    api = {
        "cm": sorted(set(re.findall(r"(?:campaign_manager|episodic_scripting|cm):([a-z_0-9]+)\s*\(", cm_doc))),
        "core": sorted(set(re.findall(r"core:([a-z_0-9]+)\s*\(", get("campaign/core.html")))),
        # model events (engine list) + UI events documented in core/uicomponent/common
        "events": sorted(set(re.findall(r"\b([A-Z][A-Za-z]+)\b", get("scripting_doc.html")))
                         | set(re.findall(r"\b(Component[A-Z][A-Za-z]+)\b", get("campaign/core.html", "campaign/uicomponent.html", "campaign/common.html")))),
        # every identifier of the interface docs: used to check object methods
        "methods": sorted(set(re.findall(r"\b([a-z_][a-z0-9_]*)\b", get("scripting_doc.html", "campaign/model_hierarchy.html") + cm_doc))),
        "ui_methods": sorted(set(re.findall(r"uicomponent:([A-Za-z]+)\s*\(", get("campaign/uicomponent.html")))),
    }
    with open(os.path.join(ROOT, "tools", "wh3_api_names.json"), "w", encoding="utf-8") as f:
        json.dump(api, f, indent=0)
    print({k: len(v) for k, v in api.items()})


if __name__ == "__main__":
    main()
