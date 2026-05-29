from __future__ import annotations

from app.services import web_search_service


def test_clean_bing_url_decodes_redirect() -> None:
    target = "https://vi.wikipedia.org/wiki/T%C6%B0_t%C6%B0%E1%BB%9Fng_H%E1%BB%93_Ch%C3%AD_Minh"

    # Bing uses URL-safe base64 after the "a1" prefix, not hex. Build it here
    # without importing implementation details into the assertion.
    import base64

    encoded = "a1" + base64.urlsafe_b64encode(target.encode("utf-8")).decode("ascii").rstrip("=")
    raw = f"https://www.bing.com/ck/a?!&&u={encoded}&ntb=1"

    assert web_search_service._clean_bing_url(raw) == target


def test_search_web_falls_back_to_bing(monkeypatch) -> None:
    html = """
    <html><body>
      <ol>
        <li class="b_algo">
          <h2>
            <a href="https://example.edu/article">Tư tưởng Hồ Chí Minh</a>
          </h2>
          <div class="b_caption"><p>Vietnamese search result snippet.</p></div>
        </li>
      </ol>
    </body></html>
    """

    class Response:
        text = html

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(web_search_service, "_search_duckduckgo", lambda query, limit: [])
    monkeypatch.setattr(web_search_service.requests, "get", lambda *args, **kwargs: Response())

    results = web_search_service.search_web("tư tưởng hồ chí minh", 5)

    assert len(results) == 1
    assert results[0].title == "Tư tưởng Hồ Chí Minh"
    assert results[0].url == "https://example.edu/article"
    assert results[0].domain == "example.edu"
