"""Tests for URL normalization."""

import pytest

from synthorg.communication.citation.normalizer import normalize_url


@pytest.mark.unit
class TestNormalizeUrl:
    """URL normalization for citation deduplication."""

    def test_lowercase_scheme(self) -> None:
        assert normalize_url("HTTP://example.com/page") == "http://example.com/page"

    def test_lowercase_host(self) -> None:
        assert normalize_url("http://EXAMPLE.COM/page") == "http://example.com/page"

    def test_mixed_case_scheme_and_host(self) -> None:
        result = normalize_url("HTTPS://Example.Com/Path")
        assert result == "https://example.com/Path"

    def test_strip_default_http_port(self) -> None:
        assert normalize_url("http://example.com:80/page") == "http://example.com/page"

    def test_strip_default_https_port(self) -> None:
        result = normalize_url("https://example.com:443/page")
        assert result == "https://example.com/page"

    def test_preserve_non_default_port(self) -> None:
        result = normalize_url("http://example.com:8080/page")
        assert result == "http://example.com:8080/page"

    def test_remove_fragment(self) -> None:
        result = normalize_url("http://example.com/page#section")
        assert result == "http://example.com/page"

    def test_remove_fragment_with_query(self) -> None:
        result = normalize_url("http://example.com/page?q=1#section")
        assert result == "http://example.com/page?q=1"

    def test_sort_query_params(self) -> None:
        result = normalize_url("http://example.com/page?z=1&a=2&m=3")
        assert result == "http://example.com/page?a=2&m=3&z=1"

    def test_sort_query_params_preserves_values(self) -> None:
        result = normalize_url("http://example.com/?b=hello&a=world")
        assert result == "http://example.com?a=world&b=hello"

    def test_strip_trailing_slash(self) -> None:
        assert normalize_url("http://example.com/") == "http://example.com"

    def test_strip_trailing_slash_on_path(self) -> None:
        assert normalize_url("http://example.com/path/") == "http://example.com/path"

    def test_no_trailing_slash_preserved(self) -> None:
        assert normalize_url("http://example.com/path") == "http://example.com/path"

    def test_idempotency(self) -> None:
        url = "https://example.com/page?a=1&b=2"
        assert normalize_url(normalize_url(url)) == normalize_url(url)

    def test_empty_query_string(self) -> None:
        result = normalize_url("http://example.com/page?")
        assert result == "http://example.com/page"

    def test_preserves_path_case(self) -> None:
        result = normalize_url("http://example.com/CaseSensitive/Path")
        assert result == "http://example.com/CaseSensitive/Path"

    def test_complex_url(self) -> None:
        url = "HTTPS://API.Example.COM:443/v1/data?limit=10&offset=0&sort=name#results"
        expected = "https://api.example.com/v1/data?limit=10&offset=0&sort=name"
        assert normalize_url(url) == expected

    def test_query_param_with_encoded_values(self) -> None:
        result = normalize_url("http://example.com/search?q=hello+world&lang=en")
        assert result == "http://example.com/search?lang=en&q=hello+world"

    def test_duplicate_query_params_preserved(self) -> None:
        result = normalize_url("http://example.com/?a=1&a=2")
        assert result == "http://example.com?a=1&a=2"

    def test_ipv6_bracketed_host(self) -> None:
        result = normalize_url("http://[2001:db8::1]/path?x=1")
        assert result == "http://[2001:db8::1]/path?x=1"

    def test_ipv6_strips_default_port(self) -> None:
        result = normalize_url("https://[::1]:443/api")
        assert result == "https://[::1]/api"

    def test_credentials_stripped(self) -> None:
        result = normalize_url("https://user:pass@example.com/path")
        assert result == "https://example.com/path"
