import pytest

from draft_helper.auth import YahooAuthError, extract_code


def test_extract_code_bare_code_passthrough():
    assert extract_code("  abc123  ") == "abc123"


def test_extract_code_from_redirect_url():
    url = "https://localhost:8080/?code=xyz789&state=foo"
    assert extract_code(url) == "xyz789"


def test_extract_code_from_url_missing_code_raises():
    with pytest.raises(YahooAuthError):
        extract_code("https://localhost:8080/?state=foo")
