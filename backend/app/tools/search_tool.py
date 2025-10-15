from typing import List
try:
    from duckduckgo_search import DDGS
except Exception:
    DDGS = None

class SearchTool:
    def search(self, query: str, max_results: int = 3) -> List[str]:
        if DDGS is None:
            return [f"[placeholder] Search results for: {query} (install duckduckgo-search)"]
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            out = []
            for r in results:
                title = r.get("title","")
                href = r.get("href","")
                body = r.get("body","")
                out.append(f"{title} — {href} — {body}")
            return out
