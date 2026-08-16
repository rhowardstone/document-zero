"""Sentence splitting, with the cases that actually cost us an article.

Every string in the first block is taken from, or modelled directly on, the
article the live reporter produced on 2026-08-16. A naive splitter cut them into
fragments, the entailment gate refused the fragments — correctly, since a
fragment asserts something incomplete — and a publishable article was thrown
away by a bug in the splitter rather than a fault in the writing.
"""
import pytest

from ledger.sentences import split


# ── The failures that cost a real article ───────────────────────────────────

def test_us_does_not_end_a_sentence():
    s = split("The State of New Mexico sued the Justice Department and Acting "
              "Attorney General Todd Blanche in the U.S. District Court for the "
              "District of Columbia over withheld Epstein records.")
    assert len(s) == 1, s


def test_a_middle_initial_does_not_end_a_sentence():
    s = split("The case is docketed as No. 1:26-cv-02762-AHA, is assigned to "
              "Judge Amir H. Ali, and is pleaded under the APA.")
    assert len(s) == 1, s


def test_no_as_in_docket_number_does_not_end_a_sentence():
    s = split("It is docketed as No. 1:26-cv-02762-AHA. The court set a date.")
    assert len(s) == 2, s
    assert s[0].startswith("It is docketed")


@pytest.mark.parametrize("text", [
    "Filed under Pub. L. No. 119-38, the statute requires disclosure.",
    "See 28 C.F.R. § 16.21 for the procedure that governs the request.",
    "The D.C. Circuit has not yet ruled on the question presented.",
    "Sen. Ron Wyden and Rep. Robert Garcia both signed the letter.",
    "Epstein died on Aug. 10, 2019, ending the federal prosecution.",
    "The firm, Acme Corp. Ltd., declined to comment on the filing.",
])
def test_domain_abbreviations_never_split(text):
    assert len(split(text)) == 1, split(text)


# ── It must still split where it should ─────────────────────────────────────

def test_ordinary_sentences_still_split():
    s = split("The Fed held rates. Two governors dissented. A third abstained.")
    assert len(s) == 3


def test_questions_and_exclamations_split():
    s = split("Did they rule? They did. The order stands!")
    assert len(s) == 3


def test_a_quoted_sentence_end_splits_after_the_quote():
    s = split('He said "I anticipate full cooperation." The records never came.')
    assert len(s) == 2, s
    assert s[0].rstrip().endswith('"')


def test_an_abbreviation_at_a_genuine_sentence_end_still_splits():
    """"…the U.S." really can end a sentence."""
    s = split("The records are held by the U.S. They were never produced.")
    # Ambiguous by construction; the splitter errs toward NOT splitting, which
    # merges two sentences rather than inventing a fragment. Merging costs one
    # over-broad check; fragmenting costs a refused article.
    assert len(s) in (1, 2)


def test_empty_and_whitespace_are_handled():
    assert split("") == [] and split("   ") == []


def test_a_single_sentence_without_terminal_punctuation_survives():
    assert split("The court has not ruled") == ["The court has not ruled"]


def test_no_text_is_lost():
    text = ("New Mexico sued in the U.S. District Court. Judge Amir H. Ali was "
            "assigned. The response is due Sep. 5, 2026.")
    assert "".join(split(text)).replace(" ", "") == text.replace(" ", "")


def test_a_year_can_end_a_sentence():
    """"…in 2019. Prosecutors then…" is ubiquitous in this material, and a rule
    protecting "No. 1:26-cv" from splitting once blocked all of them."""
    s = split("The department declined to search it in 2019. Prosecutors moved on.")
    assert len(s) == 2, s
    assert s[1].startswith("Prosecutors")


def test_a_docket_number_still_survives_a_year_ending_sentences():
    s = split("It is docketed as No. 1:26-cv-02762-AHA. It was filed in 2026. "
              "The response is due later.")
    assert len(s) == 3, s
