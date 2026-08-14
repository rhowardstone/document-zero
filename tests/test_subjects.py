"""The subject resolver is what makes two of the three refusal gates real.

These tests pin the bias: evidence grants public status, absence of evidence
does not. Over-refusal is correct behaviour here and is asserted as such.
"""
import pytest

from ledger.refusal import refusal_check
from ledger.subjects import candidate_names, is_title_case, resolve, resolver


def c(text, **kw):
    return {"claim_text": text, "quote": kw.pop("quote", ""), **kw}


# ── Finding names ────────────────────────────────────────────────────────────

def test_a_plain_name_is_a_candidate():
    assert "Bill Richardson" in candidate_names("Bill Richardson signed the order.")


def test_organisations_are_not_people():
    names = candidate_names(
        "The Justice Department and Deutsche Bank AG told the Southern District "
        "Court that San Rafael Ranch LLC had filed.")
    assert names == [], names


def test_jurisdictions_and_months_are_not_people():
    assert candidate_names("United States officials said in August 2019 that New "
                           "Mexico and the District of Columbia disagreed.") == []


def test_a_single_capitalised_word_is_not_a_name():
    """Sentence-initial capitals would otherwise flood the resolver."""
    assert candidate_names("Federal prosecutors said Tuesday that charges follow.") == []


# ── Granting public status ───────────────────────────────────────────────────

def test_a_title_before_the_name_grants_public_official():
    s = resolve(c("Attorney General Raul Torrez sued the Department of Justice."))
    assert [x.status for x in s if x.name == "Raul Torrez"] == ["public_official"]


def test_apposition_grants_public_status_too():
    s = resolve(c("Bill Richardson, then governor of New Mexico, was briefed."))
    assert next(x for x in s if x.name == "Bill Richardson").is_public


def test_a_case_caption_makes_someone_a_named_party():
    s = resolve(c("The docket in United States v. Luigi Mangione was updated."))
    assert next(x for x in s if "Mangione" in x.name).status == "named_party"


def test_a_corporate_role_grants_public_figure():
    s = resolve(c("Chief executive Marcus Halloway approved the transfer."))
    assert next(x for x in s if x.name == "Marcus Halloway").status == "public_figure"


def test_the_roster_can_grant_status_the_text_does_not():
    s = resolve(c("Jeffrey Epstein wired the funds."),
                roster={"Jeffrey Epstein": "named_party"})
    assert next(x for x in s if x.name == "Jeffrey Epstein").status == "named_party"


# ── Refusing by default ──────────────────────────────────────────────────────

def test_an_unrecognised_name_is_private_not_public():
    s = resolve(c("Deborah Vance moved the funds offshore."))
    assert [x.status for x in s] == ["unknown"]
    assert not s[0].is_public


def test_the_gate_now_actually_fires_on_a_private_individual():
    """This is the bug: with an empty resolver this claim published."""
    claim = c("Deborah Vance embezzled from the trust.")
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_the_same_accusation_about_an_official_is_not_refused_by_the_person_gate():
    claim = c("Attorney General Raul Torrez concealed the 2019 stand-down request.",
              source_type="documentation")
    d = refusal_check(claim, resolve(claim))
    assert d.gate != "wrongdoing_by_private_individual"


def test_identification_of_a_private_individual_is_refused():
    claim = c("Deborah Vance lives at 214 Mercer Street.")
    d = refusal_check(claim, resolve(claim))
    assert d.allowed is False
    assert d.gate == "identification_of_private_individual"


def test_the_quote_is_searched_for_subjects_not_only_the_claim():
    """A name that appears only in the quote is still a person the claim is about."""
    claim = {"claim_text": "The transfer was fraudulent.",
             "quote": "Deborah Vance signed the wire instruction."}
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_over_refusal_is_the_documented_failure_mode():
    """An unrostered public figure with no title in the text IS refused. This is
    intentional: a missed story is cheaper than an automated accusation."""
    claim = c("Ghislaine Maxwell was convicted of conspiracy.", source_type="article")
    assert refusal_check(claim, resolve(claim)).allowed is False
    # ...and the roster is the documented cure.
    r = resolver({"Ghislaine Maxwell": "named_party"})
    assert refusal_check(claim, r(claim)).allowed is True


def test_a_claim_about_no_person_at_all_passes_the_person_gates():
    claim = c("The Bureau of Prisons withheld 47 pages of the log.",
              source_type="documentation")
    assert refusal_check(claim, resolve(claim)).allowed is True


def test_resolver_returns_a_callable_shaped_for_the_agent():
    r = resolver({"Bill Richardson": "public_official"})
    assert r(c("Bill Richardson signed it."))[0].status == "public_official"


# ── Headline Title Case ──────────────────────────────────────────────────────
# Measured against the real corpus: bare capitalisation read headline fragments
# as people and refused institutional accountability claims on their behalf.

@pytest.mark.parametrize("headline", [
    "Epstein Files Update: Trump DOJ Accused of Noncompliance After Hearing",
    "After Year of Depositions, Comer Promises Criminal Referrals by Christmas",
    "Senate Report Details Bank Concerns Over Suspicious Transfers",
    "Court Filing Reveals New Timeline in Records Dispute",
])
def test_headline_fragments_are_not_mistaken_for_people(headline):
    assert candidate_names(headline) == [], candidate_names(headline)


def test_an_institutional_accusation_is_not_refused_as_a_private_matter():
    """The principle is scrutiny pointed UP. This is the failure that inverted it."""
    claim = c("Trump DOJ Accused of Noncompliance After Hearing")
    assert refusal_check(claim, resolve(claim)).allowed is True


def test_real_names_still_survive_the_common_word_filter():
    assert candidate_names("Deborah Vance and Marcus Halloway met.") == \
        ["Deborah Vance", "Marcus Halloway"]


def test_surnames_that_are_also_common_nouns_are_kept():
    """Baker, Cook, Green and Young are surnames; dropping them loses real
    protection, so they are deliberately absent from the common-word list."""
    for n in ("Sarah Baker", "Thomas Cook", "Alice Green", "Robert Young",
              "Marcus Wood", "Helen Price"):
        assert candidate_names(f"{n} moved the money.") == [n], n


def test_an_abbreviated_title_grants_status_despite_its_trailing_period():
    """\\b does not match between "." and " ", so Rep./Sen./Gov. silently failed."""
    for pre in ("Rep.", "Sen.", "Gov."):
        s = resolve(c(f"{pre} Robert Garcia concealed the memo."))
        got = next(x for x in s if x.name == "Robert Garcia")
        assert got.status == "public_official", (pre, got)


def test_party_labels_are_not_names():
    assert candidate_names("Republican Rep Christmas Democrats spoke.") == []


# ── Casing is judged per field ───────────────────────────────────────────────

def test_title_case_is_detected():
    assert is_title_case("Epstein Files Update: DOJ Accused of Noncompliance")
    assert not is_title_case("Federal prosecutors said the department withheld it.")
    assert not is_title_case("Deborah Vance signed it.")   # too short to judge


def test_headline_capitals_do_not_invent_a_private_individual():
    claim = c("Absolutely Reprehensible: Senator Slams Nasty As Incumbent Is Accused")
    assert [s.name for s in resolve(claim) if not s.is_public] == []
    assert refusal_check(claim, resolve(claim)).allowed is True


def test_a_private_person_in_sentence_case_is_still_protected():
    """The headline rule must not disable the gate on ordinary prose."""
    claim = c("Deborah Vance embezzled from the trust.")
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_casing_is_judged_per_field_not_across_the_claim():
    """A headline quote must not switch off detection for a sentence-case claim."""
    claim = {"claim_text": "The wire was authorised by Deborah Vance, who signed it.",
             "quote": "DOJ Accused Of Noncompliance After Lengthy Records Hearing"}
    assert any(s.name == "Deborah Vance" and not s.is_public for s in resolve(claim))


def test_a_possessive_still_matches_the_roster():
    """The token pattern allows apostrophes so O'Brien survives; possessives rode
    along and missed the roster by exact match."""
    s = resolve(c("Jeffrey Epstein’s estate transferred the property."),
                roster={"Jeffrey Epstein": "named_party"})
    assert next(x for x in s if "Epstein" in x.name).status == "named_party"


def test_names_with_apostrophes_are_not_mangled():
    assert "Siobhan O’Brien" in [x.name for x in
        resolve(c("Siobhan O’Brien moved the funds."))]


def test_a_title_inside_the_name_span_still_grants_status():
    """"Judge Emmet Sullivan" is one capitalised span; the title is not before
    the name, it IS the start of it. A federal judge was filed as private."""
    s = resolve(c("Judge Emmet Sullivan demanded a DOJ explanation."))
    assert all(x.is_public for x in s), s


def test_scraper_furniture_is_not_a_person():
    for junk in ("Add Yahoo", "Trump Yahoo", "Nashville Banner", "Interlochen Center"):
        assert candidate_names(f"{junk} said the files were withheld.") == [], junk


def test_headline_evaluative_language_is_not_a_person():
    for junk in ("Absolutely Reprehensible", "Nasty As", "Shocking Circumstances"):
        assert candidate_names(f"{junk} conduct was alleged.") == [], junk


# ── The harmful direction: a private individual escaping the gate ────────────
# Every case below published an accusation about a private person before it was
# fixed. Over-refusal is the intended failure; this is the other one.

def test_a_headline_cased_accusation_still_protects_the_person():
    """Casing is a reason to be unsure, and unsure means refuse. Dropping the
    subject because the text was Title Case disabled the gate entirely."""
    claim = c("Alice Smith: Allegedly Lied About Charity Funds In Community Work")
    d = refusal_check(claim, resolve(claim))
    assert d.allowed is False, [(s.name, s.status) for s in resolve(claim)]
    assert d.gate == "wrongdoing_by_private_individual"


def test_a_title_does_not_leak_across_a_sentence_boundary():
    """"CEO Robert Jones spoke today. Alice Smith lied about the charity." made
    Alice Smith a public figure because CEO fell inside a flat 60-char window."""
    claim = c("CEO Robert Jones spoke today. Alice Smith lied about the charity.")
    got = {s.name: s.status for s in resolve(claim)}
    assert got["Robert Jones"] == "public_figure"
    assert got["Alice Smith"] == "unknown", got
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_a_bare_surname_in_a_caption_does_not_make_someone_a_party():
    """"Smith v. Jones" does not tell you WHICH Smith."""
    claim = c("Smith v. Jones was cited. Alice Smith lied about the charity.")
    got = {s.name: s.status for s in resolve(claim)}
    assert got.get("Alice Smith") == "unknown", got
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_a_doctorate_is_not_an_office():
    s_ = resolve(c("Dr. Robert Garcia concealed the memo."))
    assert all(not x.is_public for x in s_), s_


def test_an_abbreviated_title_survives_sentence_splitting():
    """A period after "Rep." is an abbreviation, not a sentence end."""
    # "Dr." is deliberately absent: a physician is not a public official, and a
    # doctorate is not an office. Someone titled only "Dr." stays protected.
    for pre in ("Rep.", "Sen.", "Gov."):
        s_ = resolve(c(f"{pre} Robert Garcia concealed the memo."))
        assert any(x.is_public for x in s_), (pre, s_)


def test_apposition_after_the_name_still_grants_status():
    s_ = resolve(c("Bill Richardson, then governor of New Mexico, was briefed."))
    assert next(x for x in s_ if x.name == "Bill Richardson").is_public


def test_a_following_clause_about_someone_else_does_not_grant_status():
    claim = c("Alice Smith lied about the charity. The governor responded.")
    assert {s.name: s.status for s in resolve(claim)}.get("Alice Smith") == "unknown"


def test_an_all_caps_name_is_not_erased():
    """Erasure is as harmful as misclassification: no subject, no gate."""
    claim = c("DEBORAH VANCE lied about the missing funds.")
    assert refusal_check(claim, resolve(claim)).allowed is False


def test_a_non_ascii_capital_is_not_erased():
    for n in ("Élodie Martin", "Ángela Rojas", "Øystein Dahl"):
        claim = c(f"{n} lied about the missing funds.")
        assert refusal_check(claim, resolve(claim)).allowed is False, n


def test_agency_acronyms_are_still_organisations_not_people():
    for junk in ("DOJ Accused", "FBI Albuquerque", "SDNY Prosecutors", "NMDOJ Investigators"):
        assert candidate_names(f"{junk} withheld the file.") == [], junk


def test_institutional_accountability_survives_all_the_person_fixes():
    """The whole point of the tuning: scrutiny pointed up must still publish."""
    for headline in ("Trump DOJ Accused of Noncompliance After Hearing",
                     "FBI Withheld Records From State Investigators",
                     "Senate Report Details Bank Concerns Over Suspicious Transfers"):
        claim = c(headline, source_type="documentation")
        assert refusal_check(claim, resolve(claim)).allowed is True, \
            (headline, [(s.name, s.status) for s in resolve(claim)])
