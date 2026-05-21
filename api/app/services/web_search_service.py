"""
Web Search Service — DuckDuckGo-based web search + URL preview.

Provides two main capabilities:
1. search_web(): keyword → list of web results (title, url, snippet, domain)
2. fetch_web_preview(): url → scraped preview (title, content, tags, meta)

Designed to be swappable with SerpAPI / Tavily by changing the provider in config.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.ingestion_service import fetch_web_article


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

class WebSearchResult:
    def __init__(
        self,
        title: str,
        url: str,
        snippet: str,
        domain: str,
        favicon_url: str | None = None,
    ) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet
        self.domain = domain
        self.favicon_url = favicon_url

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "domain": self.domain,
            "favicon_url": self.favicon_url,
        }


class WebPreviewResult:
    def __init__(
        self,
        url: str,
        title: str,
        domain: str,
        description: str | None = None,
        content_preview: str = "",
        full_content: str = "",
        estimated_word_count: int = 0,
        favicon_url: str | None = None,
        published_at: str | None = None,
        author: str | None = None,
        tags: list[str] | None = None,
        language: str | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.domain = domain
        self.description = description
        self.content_preview = content_preview
        self.full_content = full_content
        self.estimated_word_count = estimated_word_count
        self.favicon_url = favicon_url
        self.published_at = published_at
        self.author = author
        self.tags = tags or []
        self.language = language

    @property
    def estimated_reading_time_minutes(self) -> int:
        # Average reading speed: 200 words/min
        return max(1, round(self.estimated_word_count / 200))

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "content_preview": self.content_preview,
            "estimated_word_count": self.estimated_word_count,
            "estimated_reading_time_minutes": self.estimated_reading_time_minutes,
            "favicon_url": self.favicon_url,
            "published_at": self.published_at,
            "author": self.author,
            "tags": self.tags,
            "language": self.language,
        }


# ---------------------------------------------------------------------------
# DuckDuckGo search (no API key required)
# ---------------------------------------------------------------------------

_DDG_SEARCH_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def search_web(query: str, limit: int = 10) -> list[WebSearchResult]:
    """
    Search the web for the given query using DuckDuckGo.
    Returns up to `limit` results.
    """
    settings = get_settings()
    effective_limit = min(limit, settings.web_search_max_results)

    provider = settings.web_search_provider
    if provider == "serpapi":
        return _search_serpapi(query, effective_limit)
    # Default: DuckDuckGo (no key required)
    return _search_duckduckgo(query, effective_limit)


def _search_duckduckgo(query: str, limit: int) -> list[WebSearchResult]:
    """Parse DuckDuckGo HTML search results."""
    try:
        response = requests.post(
            _DDG_SEARCH_URL,
            data={"q": query, "b": "", "kl": ""},
            headers=_HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WebSearchError(f"DuckDuckGo search failed: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    results: list[WebSearchResult] = []

    # DuckDuckGo HTML layout: .result__body divs
    for result_div in soup.select(".result__body"):
        if len(results) >= limit:
            break

        # Title + URL
        title_tag = result_div.select_one(".result__title a")
        if not title_tag:
            continue
        raw_url = title_tag.get("href", "")
        url = _clean_ddg_url(str(raw_url))
        if not url or not url.startswith("http"):
            continue
        title = title_tag.get_text(" ", strip=True)

        # Snippet
        snippet_tag = result_div.select_one(".result__snippet")
        snippet = snippet_tag.get_text(" ", strip=True) if snippet_tag else ""

        domain = _extract_domain(url)
        favicon_url = _favicon_url(domain)

        results.append(
            WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                domain=domain,
                favicon_url=favicon_url,
            )
        )

    return results


def _search_serpapi(query: str, limit: int) -> list[WebSearchResult]:
    """SerpAPI-based search (requires SERP_API_KEY in config)."""
    settings = get_settings()
    api_key = settings.web_search_api_key
    if not api_key:
        raise WebSearchError("SerpAPI key not configured (WEB_SEARCH_API_KEY).")

    try:
        response = requests.get(
            "https://serpapi.com/search",
            params={
                "q": query,
                "api_key": api_key,
                "num": limit,
                "engine": "google",
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        raise WebSearchError(f"SerpAPI search failed: {exc}") from exc

    results: list[WebSearchResult] = []
    for item in data.get("organic_results", [])[:limit]:
        url = item.get("link", "")
        domain = _extract_domain(url)
        results.append(
            WebSearchResult(
                title=item.get("title", ""),
                url=url,
                snippet=item.get("snippet", ""),
                domain=domain,
                favicon_url=_favicon_url(domain),
            )
        )
    return results


# ---------------------------------------------------------------------------
# URL preview (reuses ingestion_service scraping logic)
# ---------------------------------------------------------------------------

def fetch_web_preview(url: str) -> WebPreviewResult:
    """
    Fetch and parse a URL to produce a rich preview card.
    Reuses fetch_web_article() from ingestion_service to scrape content.
    """
    try:
        article = fetch_web_article(url)
    except Exception as exc:
        raise WebPreviewError(f"Failed to preview URL '{url}': {exc}") from exc

    domain = _extract_domain(url)
    full_content: str = article.get("content", "") or ""
    word_count = len(full_content.split())
    content_preview = " ".join(full_content.split()[:120])  # ~120 words preview

    # Extract description from meta if available (fetch_web_article doesn't return it,
    # so we do a lightweight re-fetch for meta description only)
    description = _fetch_meta_description(url)

    tags: list[str] = article.get("tags", []) or []

    return WebPreviewResult(
        url=url,
        title=article.get("title") or url,
        domain=domain,
        description=description,
        content_preview=content_preview,
        full_content=full_content,
        estimated_word_count=word_count,
        favicon_url=_favicon_url(domain),
        published_at=article.get("published_at"),
        author=article.get("author"),
        tags=tags,
        language=article.get("language"),
    )


def _fetch_meta_description(url: str) -> str | None:
    """Lightweight fetch of only the <meta name='description'> tag."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10, stream=True)
        resp.raise_for_status()
        # Read only first 16KB to find meta tags efficiently
        partial = b""
        for chunk in resp.iter_content(chunk_size=4096):
            partial += chunk
            if len(partial) > 16384:
                break
        soup = BeautifulSoup(partial, "html.parser")
        for name in ("description", "og:description", "twitter:description"):
            tag = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            if tag and tag.get("content"):
                return str(tag["content"]).strip()[:500]
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


def _favicon_url(domain: str) -> str:
    """Use Google's favicon service for reliable favicon resolution."""
    return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"


def _clean_ddg_url(raw: str) -> str:
    """DuckDuckGo wraps URLs in redirect links — extract the real URL."""
    if raw.startswith("//duckduckgo.com/l/?"):
        # Extract uddg= param
        match = re.search(r"uddg=([^&]+)", raw)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))
    # Sometimes they're relative without the domain
    if raw.startswith("/l/?"):
        match = re.search(r"uddg=([^&]+)", raw)
        if match:
            from urllib.parse import unquote
            return unquote(match.group(1))
    return raw


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class WebSearchError(Exception):
    pass


class WebPreviewError(Exception):
    pass
