"""Zero-key multi-source retrieval for fully agent-native operation.

Uses only free, no-API-key sources:
- DuckDuckGo via the `ddgs` package (pip install ddgs)
- Wikipedia REST API

Falls back gracefully if packages or network are unavailable.
"""

from __future__ import annotations
from typing import List, Dict, Any
import urllib.request
import urllib.parse
import json

def wikipedia_summary(query: str, limit: int = 2) -> List[Dict[str, Any]]:
    results = []
    try:
        # Search first
        search_url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": limit
        })
        req = urllib.request.Request(search_url, headers={"User-Agent": "VeritasAgent/0.3"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("query", {}).get("search", [])[:limit]:
            title = item.get("title", "")
            # Get summary
            sum_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            req2 = urllib.request.Request(sum_url, headers={"User-Agent": "VeritasAgent/0.3"})
            with urllib.request.urlopen(req2, timeout=8) as resp2:
                sdata = json.loads(resp2.read().decode())
            extract = sdata.get("extract", item.get("snippet", ""))
            results.append({
                "url": sdata.get("content_urls", {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}",
                "title": title,
                "text": extract[:800]
            })
    except Exception:
        pass
    return results

def duckduckgo_search(query: str, max_results: int = 4) -> List[Dict[str, Any]]:
    results = []
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "url": r.get("href") or r.get("link") or "",
                    "title": r.get("title") or "",
                    "text": (r.get("body") or r.get("snippet") or "")[:600]
                })
    except Exception:
        # Fallback: DuckDuckGo Instant Answer (no key)
        try:
            url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
                "q": query, "format": "json", "no_html": 1
            })
            req = urllib.request.Request(url, headers={"User-Agent": "VeritasAgent/0.3"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
            if data.get("Abstract"):
                results.append({
                    "url": data.get("AbstractURL") or "https://duckduckgo.com",
                    "title": data.get("Heading") or query,
                    "text": data.get("Abstract")[:600]
                })
        except Exception:
            pass
    return results

def free_retrieve(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Primary zero-key retrieval entry point."""
    results = []
    results.extend(wikipedia_summary(query, limit=2))
    results.extend(duckduckgo_search(query, max_results=max(2, max_results - len(results))))
    # Deduplicate by URL
    seen = set()
    unique = []
    for r in results:
        u = r.get("url") or ""
        if u and u not in seen:
            seen.add(u)
            unique.append(r)
    return unique[:max_results]

if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) or "x402 protocol"
    for r in free_retrieve(q):
        print(r["title"], "-", r["url"])
        print(r["text"][:150], "...\n")
