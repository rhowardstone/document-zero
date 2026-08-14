import pytest
from ledger.ceilings import ceiling_for, check_confidence, CeilingError, requires_doi

def test_known_ceilings():
    for t, c in [("article",1.0),("inproceedings",0.95),("preprint",0.85),("techreport",0.8),
                 ("book",0.9),("documentation",0.85),("repo",0.8),("blog",0.7),
                 ("news",0.6),("misc",0.5)]:
        assert ceiling_for(t) == c

def test_unknown_source_type_falls_to_misc_ceiling():
    assert ceiling_for("pigeon") == 0.5

def test_news_claim_at_ceiling_is_accepted():
    check_confidence("news", 0.6)

def test_news_claim_above_ceiling_is_rejected():
    with pytest.raises(CeilingError) as e:
        check_confidence("news", 0.61)
    assert "0.6" in str(e.value) and "news" in str(e.value)

def test_confidence_out_of_range_is_rejected():
    with pytest.raises(CeilingError): check_confidence("article", 1.4)
    with pytest.raises(CeilingError): check_confidence("article", -0.1)

def test_doi_requirement_by_type():
    assert requires_doi("article") and requires_doi("inproceedings") and requires_doi("preprint")
    assert not requires_doi("news") and not requires_doi("documentation")
