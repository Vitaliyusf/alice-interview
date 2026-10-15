import pytest

from sitemap.links import is_excluded, normalize, same_host


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://Example.com/about/", "https://example.com/about"),
        ("https://example.com/a?x=1#top", "https://example.com/a"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com", "https://example.com"),
    ],
)
def test_normalize_drops_query_fragment_and_trailing_slash(raw, expected):
    assert normalize(raw) == expected


def test_same_host_treats_www_as_same_site_and_subdomains_as_other():
    assert same_host("https://www.example.com/x", "https://example.com")
    assert not same_host("https://blog.example.com/x", "https://example.com")
    assert not same_host("https://other.com", "https://example.com")


@pytest.mark.parametrize(
    "url",
    [
        "mailto:a@example.com",
        "tel:+123",
        "javascript:void(0)",
        "https://example.com/brochure.PDF",
        "https://example.com/img/logo.png",
        "https://example.com/files/a.zip",
        "https://example.com/login",
        "https://example.com/account/settings",
        "https://example.com/signup",
        "https://example.com/es/about",
        "https://example.com/fr",
        "https://example.com/zh-cn/products",
        "https://example.com/hi",
        "https://example.com/uk/",
        "https://example.com/zh-hant",
        "https://example.com/pt-br/docs",
        "https://example.com/blog/tag/python",
        "https://example.com/blog/page/2",
    ],
)
def test_is_excluded_rejects_non_page_urls(url):
    assert is_excluded(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/about",
        "https://example.com/esports",
        "https://example.com/blog/page-layout",
        "https://example.com/pricing",
        "https://example.com/learn",
        "https://example.com/features",
        "https://example.com/docs/es/intro",
    ],
)
def test_is_excluded_keeps_content_pages(url):
    assert not is_excluded(url)
