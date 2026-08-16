"""The reader must not be served yesterday's front page.

Measured on the live site: index.html comes back `cache-control: no-cache`
(Cloudflare marks it DYNAMIC), but data.js — which is where every headline,
date and paragraph actually lives — came back `max-age=14400` with
`cf-cache-status: EXPIRED`. Cloudflare caches by extension and applies its own
four-hour browser TTL to .js, overriding the origin's `expires -1`.

So for four hours after publication a reader could load a page whose masthead
said one date and whose stories were from the day before. For a newspaper that
is not a performance issue, it is a correctness one — and it is the same class
of bug as every other in this project: something stating what it does not know.

The fix belongs on our side of the wire rather than in a dashboard setting,
because a dashboard setting is not in the repo, is not tested, and cannot be
reviewed. index.html is always fresh, so the edition's fingerprint travels in
the URL it asks for.
"""
from ledger.cachebust import fingerprint, stamp

PAGE = '<head><script src="data.js"></script></head>'


def test_the_script_url_carries_the_edition_fingerprint():
    out = stamp(PAGE, "window.DZ = {}")
    assert 'src="data.js?v=' in out and out != PAGE


def test_the_same_edition_produces_the_same_url():
    """A stable page must not appear to change when nothing has."""
    assert stamp(PAGE, "same") == stamp(PAGE, "same")


def test_a_new_edition_produces_a_new_url():
    assert stamp(PAGE, "monday") != stamp(PAGE, "tuesday")


def test_restamping_replaces_the_old_fingerprint_rather_than_appending():
    once = stamp(PAGE, "monday")
    twice = stamp(once, "tuesday")
    assert twice.count("?v=") == 1 and twice == stamp(PAGE, "tuesday")


def test_nothing_else_on_the_page_is_touched():
    page = ('<script src="data.js"></script>'
            '<a href="data.js">the data</a><p>data.js is the ledger</p>')
    out = stamp(page, "x")
    assert '<a href="data.js">' in out and "<p>data.js is the ledger</p>" in out


def test_a_page_without_the_script_is_returned_unchanged():
    """Never fail the deploy over a page shape we did not expect."""
    assert stamp("<html><body>no script</body></html>", "x") == \
        "<html><body>no script</body></html>"


def test_single_quoted_and_spaced_attributes_are_handled():
    for page in ("<script src='data.js'></script>",
                 '<script  src = "data.js" defer></script>'):
        assert "?v=" in stamp(page, "x"), page


def test_the_fingerprint_is_short_and_url_safe():
    fp = fingerprint("window.DZ = {}")
    assert 6 <= len(fp) <= 16 and fp.isalnum()
