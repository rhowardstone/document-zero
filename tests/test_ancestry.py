from ledger.ancestry import root_of, build_edges, detect_single_root, Edge

def c(cid, quote, url, parent=None):
    return {"id": cid, "quote": quote, "source_url": url, "parent": parent}

def test_claims_sharing_an_exact_quote_share_a_root():
    claims = [c("a", "the retention window is seven days", "https://ap.org/x"),
              c("b", "the retention window is seven days", "https://wapo.com/y"),
              c("d", "the retention window is seven days", "https://usnews.com/z")]
    edges = build_edges(claims)
    roots = {root_of(x["id"], edges) for x in claims}
    assert len(roots) == 1

def test_distinct_quotes_have_distinct_roots():
    claims = [c("a", "quote one", "https://ap.org/x"),
              c("b", "quote two", "https://reuters.com/y")]
    edges = build_edges(claims)
    assert root_of("a", edges) != root_of("b", edges)

def test_detect_single_root_flags_three_outlets_one_origin():
    claims = [c("a", "same words exactly", "https://ap.org/x"),
              c("b", "same words exactly", "https://wapo.com/y"),
              c("d", "same words exactly", "https://boston.com/z")]
    r = detect_single_root(claims)
    assert r.single_root is True
    assert r.apparent_sources == 3
    assert r.actual_roots == 1

def test_detect_single_root_passes_genuinely_independent_claims():
    claims = [c("a", "first independent wording", "https://ap.org/x"),
              c("b", "entirely different wording here", "https://reuters.com/y"),
              c("d", "a third distinct formulation", "https://nyt.com/z")]
    r = detect_single_root(claims)
    assert r.single_root is False
    assert r.actual_roots == 3

def test_explicit_parent_links_are_followed_transitively():
    edges = [Edge("c", "b"), Edge("b", "a")]
    assert root_of("c", edges) == "a"

def test_cycles_do_not_hang():
    edges = [Edge("a", "b"), Edge("b", "a")]
    assert root_of("a", edges) in ("a", "b")

def test_single_claim_is_never_single_root_flagged():
    assert detect_single_root([c("a", "x", "https://ap.org/x")]).single_root is False
