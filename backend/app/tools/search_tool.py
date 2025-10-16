from typing import List

# Prefer latest package name (ddgs), fallback to legacy (duckduckgo_search)
DDGS = None
try:
    from ddgs import DDGS as _DDGS
    DDGS = _DDGS
except Exception:
    try:
        from duckduckgo_search import DDGS as _DDGS
        DDGS = _DDGS
    except Exception:
        DDGS = None


class SearchTool:
    def search(self, query: str, max_results: int = 3) -> List[str]:
        print(f"[SearchTool] search called with query: {query}, max_results: {max_results}")
        if DDGS is None:
            return [f"[placeholder] Search results for: {query} (install ddgs)"]

        try:
            # Use broader region and a recent time window to encourage fresh results
            with DDGS() as ddgs:
                # Use minimal, broadly compatible signature to avoid library differences
                results = ddgs.text(query, max_results=int(max_results or 3))
                out: List[str] = []
                for r in results or []:
                    # r is a dict like {"title", "href", "body"}
                    title = (r.get("title") or "").strip()
                    href = (r.get("href") or "").strip()
                    body = (r.get("body") or "").strip()
                    # Skip completely empty rows
                    if not (title or href or body):
                        continue
                    out.append(f"{title} — {href} — {body}")

                if not out:
                    return [f"[no_results] No results for: {query}. Try more specific terms."]
                return out
        except Exception as e:
            return [f"[error] web_search failed: {type(e).__name__}: {e}"]
