"""Fetching the article rather than the headline.

The failure behaviour matters more than the success behaviour here. A page that
blocks us must produce thinner evidence and thinner claims, never wrong ones —
a bad extraction would put words into a claim that no journalist wrote.
"""
from ledger.fulltext import MIN_BODY_WORDS, Body, extract, fetch

LEDE = ("The State of New Mexico sued the Justice Department on Tuesday over "
        "records it says were promised in 2019, opening a fight that has been "
        "building for most of a year and that turns on a protective order.")
SECOND = ("The complaint, filed in Washington, names the acting attorney general "
          "and asks the court to compel production of unredacted files that the "
          "department has so far declined to hand over to state investigators.")


def page(*paras, extra=""):
    body = "".join(f"<p>{p}</p>" for p in paras)
    return f"<html><body>{extra}{body}</body></html>"


# ── Extraction ──────────────────────────────────────────────────────────────

def test_paragraphs_become_the_body():
    out = extract(page(LEDE, SECOND))
    assert LEDE in out and SECOND in out


def test_navigation_and_scripts_are_removed():
    html = page(LEDE, SECOND, extra="<nav><p>Home News Sport Weather Menu Search</p>"
                                    "</nav><script>var x = 'Breaking news alert';</script>")
    out = extract(html)
    assert "var x" not in out and "Home News Sport" not in out


def test_boilerplate_paragraphs_are_dropped():
    """These live in <p> tags on real news sites and are not the article."""
    for junk in ("Subscribe to our newsletter for the latest updates every morning",
                 "Your local PBS station powers PBS News and keeps it free for all",
                 "Support our independent journalism by becoming a member today now",
                 "All rights reserved. Copyright 2026 by the publishing company."):
        out = extract(page(junk, LEDE, SECOND))
        assert junk not in out, junk


def test_short_paragraphs_are_dropped():
    out = extract(page("Read more:", "By Jane Doe", LEDE, SECOND))
    assert "Read more" not in out and "Jane Doe" not in out


def test_leading_furniture_is_trimmed_until_a_real_lede():
    out = extract(page("A short promo line that slipped through the filters ok",
                       LEDE, SECOND))
    assert out.startswith("The State of New Mexico")


def test_an_empty_page_yields_nothing_rather_than_raising():
    assert extract("") == "" and extract("<html></html>") == ""


# ── Fetching, and failing ───────────────────────────────────────────────────

THIRD = ("Lawyers for the state said the department had produced thirty-one pages "
         "in response, most of them public material the state had itself supplied, "
         "and asked the judge to set a schedule before the end of the month.")
FOURTH = ("A department spokesperson declined to comment on pending litigation but "
          "pointed to earlier statements in which officials said they intended to "
          "cooperate with state investigators wherever the law allowed it.")


def test_a_good_page_produces_a_usable_body():
    b = fetch("https://x/", _opener=lambda u: (page(LEDE, SECOND, THIRD, FOURTH), u))
    assert b.ok and b.words >= MIN_BODY_WORDS and not b.error


def test_a_repeated_paragraph_is_counted_once():
    """Sites echo a standfirst in the body. Counting it twice inflates the word
    count and hands the same sentence to the reporter as two pieces of evidence."""
    once = fetch("https://x/", _opener=lambda u: (page(LEDE, SECOND, THIRD, FOURTH), u))
    twice = fetch("https://x/", _opener=lambda u: (
        page(LEDE, SECOND, THIRD, FOURTH, LEDE, SECOND), u))
    assert once.words == twice.words


def test_a_blocked_page_returns_a_thin_body_and_never_raises():
    """The caller falls back to the summary: thinner evidence, thinner claims,
    and a beat that probably degrades to a line. Less gets said, and nothing
    unsupported gets said."""
    def blocked(url):
        raise OSError("HTTP Error 403: Forbidden")
    b = fetch("https://x/", _opener=blocked)
    assert b.ok is False and "403" in b.error and b.text == ""


def test_a_page_with_almost_no_body_is_reported_as_thin():
    b = fetch("https://x/", _opener=lambda u: (page(LEDE), u))
    assert b.ok is False and "words extracted" in b.error


def test_the_final_url_after_redirects_is_kept():
    b = fetch("https://aggregator/x",
              _opener=lambda u: (page(LEDE, SECOND) * 3, "https://publisher/real"))
    assert b.url == "https://publisher/real"


def test_a_timeout_is_survivable():
    def slow(url):
        raise TimeoutError("the read operation timed out")
    assert fetch("https://x/", _opener=slow).ok is False
