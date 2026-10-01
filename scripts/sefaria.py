"""Minimal Sefaria API client (stdlib only) with polite retries.

Responses are returned in memory. Callers must mask names (names.py) before
writing anything to disk.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

BASE = "https://www.sefaria.org/api"
UA = "tehillim-study-site/0.1 (static educational site; contact via GitHub)"
MAM = "Miqra according to the Masorah"


def get_text(url: str, tries: int = 6) -> str:
    """GET a URL with retries (also used for Wikisource)."""
    delay = 2.0
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except Exception:
            if attempt == tries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def get_json(path: str, params: dict | None = None, tries: int = 6) -> dict | list:
    url = f"{BASE}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params, safe="|")
    delay = 2.0
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:  # 429/503/network: back off and retry
            if attempt == tries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def psalm_raw(n: int, version: str = MAM) -> dict:
    """Raw v3 response for one psalm. Contains unmasked text: never persist."""
    return get_json(f"v3/texts/Psalms.{n}", {"version": f"hebrew|{version}"})
