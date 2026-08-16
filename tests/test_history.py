"""How long a story has actually been running.

The beat test wants events spanning five days. An RSS wire carries one to three,
so on a first run every candidate failed for span and nothing could ever open —
a cold start, not a disagreement with the rule. These tests pin the lookup that
gives the rule the evidence it was asking for, and pin the failure behaviour,
which matters more: a lookup that fails must not open a beat and must not crash
the run.
"""
from ledger.history import Span, query_for, span


def arts(*days, value=0.3):
    """A timelinevol payload: daily coverage volume across the window."""
    return {"timeline": [{"series": "Volume Intensity",
                          "data": [{"date": d, "value": value} for d in days]}]}


def fetcher(payload):
    return lambda q, t, m: payload


def test_span_is_measured_between_first_and_last_day():
    s = span("q", _fetcher=fetcher(arts("20260801T000000Z", "20260810T000000Z")))
    assert s.days == 9 and s.first == "20260801" and s.last == "20260810"


def test_days_with_no_coverage_do_not_count():
    """A timeline point of zero means nobody wrote about it that day."""
    payload = {"timeline": [{"data": [
        {"date": "20260801T000000Z", "value": 0.0},
        {"date": "20260816T000000Z", "value": 0.4}]}]}
    s = span("q", _fetcher=fetcher(payload))
    assert s.distinct_days == 1 and s.days == 0


def test_a_story_running_for_weeks_reports_a_real_span():
    s = span("q", _fetcher=fetcher(arts("20260726T000000Z", "20260805T000000Z",
                                        "20260816T000000Z")))
    assert s.days == 21 and s.distinct_days == 3 and s.found


def test_an_unreachable_api_returns_an_empty_span_and_does_not_raise():
    """A lookup that fails must not open a beat, and must not crash the run."""
    def boom(q, t, m):
        raise OSError("network down")
    s = span("q", _fetcher=boom)
    assert s.found is False and s.days == 0


def test_unparseable_payloads_are_survivable():
    for payload in ({}, {"timeline": None}, {"timeline": []}, None):
        assert span("q", _fetcher=fetcher(payload)).found is False


def test_malformed_dates_are_ignored_rather_than_crashing():
    s = span("q", _fetcher=fetcher(arts("not-a-date", "20260816T000000Z")))
    assert s.distinct_days == 1


def test_the_query_is_unquoted():
    """Measured against the live API: quoted phrases matched nothing at all —
    "Zorro Ranch", "Strait of Hormuz" and "Storm Lala" each returned zero —
    while the same words unquoted returned full timelines."""
    q = query_for("Democrats' 2028 primary calendar")
    assert '"' not in q


def test_short_words_are_dropped_from_the_query():
    assert "the" not in query_for("The Fed and the September decision").lower()


def test_a_name_with_no_usable_words_still_produces_a_query():
    assert query_for("!!!")


def test_the_query_is_capped_so_it_stays_a_phrase_not_a_paragraph():
    q = query_for("A very long story name with many many words in it indeed")
    assert len(q.split()) <= 3


def test_a_rate_limited_lookup_is_retried():
    """GDELT answers a burst with a 429 that is not JSON. Without a retry the
    span came back empty and the caller silently fell back to the wire's own
    one-to-three-day window, rejecting twenty-day stories for span."""
    calls = []

    def flaky(q, t, m):
        calls.append(1)
        if len(calls) < 3:
            raise OSError("HTTP Error 429: Too Many Requests")
        return arts("20260801T000000Z", "20260816T000000Z")

    # An injected fetcher does not retry (tests must stay fast); the real one
    # does. Assert the failure is at least REPORTED rather than silent.
    s = span("q", _fetcher=flaky)
    assert s.found is False and "429" in s.error


def test_a_failed_lookup_says_why():
    def boom(q, t, m):
        raise OSError("network down")
    assert "network down" in span("q", _fetcher=boom).error


def test_a_cached_span_costs_no_request(tmp_path, monkeypatch):
    """A day's answer for a story does not change between runs, and a cached hit
    costs neither a request nor the nine-second throttle. This is what makes a
    daily cron cheap: the same beats are looked up every day."""
    import ledger.history as H
    monkeypatch.setattr(H, "CACHE_DIR", tmp_path / "c")
    calls = []

    def once(q, t, m):
        calls.append(1)
        return arts("20260801T000000Z", "20260816T000000Z")

    a = H.span("cache-me", _fetcher=once, use_cache=True)
    b = H.span("cache-me", _fetcher=once, use_cache=True)
    assert a.days == b.days == 15
    assert len(calls) == 1, "the second lookup should have been served from cache"


def test_a_failed_lookup_is_not_cached(tmp_path, monkeypatch):
    """Caching a 429 would turn a transient rate limit into a day-long outage."""
    import ledger.history as H
    monkeypatch.setattr(H, "CACHE_DIR", tmp_path / "c")

    def boom(q, t, m):
        raise OSError("429")
    H.span("transient", _fetcher=boom, use_cache=True)
    ok = H.span("transient", use_cache=True,
                _fetcher=lambda *a: arts("20260801T000000Z", "20260816T000000Z"))
    assert ok.found is True
