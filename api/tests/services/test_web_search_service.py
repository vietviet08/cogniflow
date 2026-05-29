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


def test_startpage_parser_extracts_relevant_result(monkeypatch) -> None:
    html = """
    <html><body>
      <div class="result">
        <a class="result-link" href="https://itviec.com/blog/cau-hoi-phong-van-java-spring-boot/">ITviec</a>
        <a class="result-link" href="https://itviec.com/blog/cau-hoi-phong-van-java-spring-boot/">
          https://itviec.com › blog › cau-hoi-phong-van-java-spring-boot
        </a>
        <a class="result-link" href="https://itviec.com/blog/cau-hoi-phong-van-java-spring-boot/">
          Top 45+ câu hỏi phỏng vấn Java Spring Boot thường gặp - ITviec Blog
        </a>
        <p>Tổng hợp các câu hỏi phỏng vấn Java Spring Boot thường gặp.</p>
      </div>
    </body></html>
    """

    class Response:
        text = html

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(web_search_service.requests, "get", lambda *args, **kwargs: Response())

    results = web_search_service._search_startpage("câu hỏi phỏng vấn java spring boot", 10)

    assert len(results) == 1
    assert results[0].title == "Top 45+ câu hỏi phỏng vấn Java Spring Boot thường gặp - ITviec Blog"
    assert results[0].url == "https://itviec.com/blog/cau-hoi-phong-van-java-spring-boot/"


def test_rank_results_filters_broad_function_word_matches() -> None:
    broad = web_search_service.WebSearchResult(
        title="Các loại câu trong tiếng Việt",
        url="https://example.test/cau",
        snippet="Bài viết về câu đơn và câu ghép.",
        domain="example.test",
    )
    relevant = web_search_service.WebSearchResult(
        title="Câu hỏi phỏng vấn Java Spring Boot",
        url="https://example.test/java-spring-boot",
        snippet="Danh sách câu hỏi Java và Spring Boot.",
        domain="example.test",
    )

    ranked = web_search_service._rank_results(
        "câu hỏi phỏng vấn java spring boot",
        [broad, relevant],
    )

    assert ranked == [relevant]
