"""Re-running a day must be safe, cheap, and honestly reported.

Articles are immutable: a correction is a new day's article, never an edit.
That rule is right and stays. But it made a normal operation — a scheduler
retry, a manual re-run after fixing one beat — look like a newsroom-wide
failure. The second full run of 2026-08-16 reported this:

    5 article(s) survived, 7 did not
      indiana-record-flooding-august-2026    reporter failed
      nm-records                             reporter failed
      us-iran-war-and-hormuz-blockade        reporter failed

Every one of those had already been written, verified and published hours
earlier. Nothing failed. The run had spent a full reporter call and two
verifier calls per beat before discovering it could not store the result.

Two things are wrong with that and both matter:

  - It reports a pipeline condition as an editorial one, exactly like the
    inherited-stdin bug. "reporter failed" is what this system says when the
    writing did not work, and a reader of that output cannot tell the
    difference between "we could not write this" and "we already did".
  - It pays for work whose result is guaranteed to be discarded.
"""
import json

from ledger.published import already_published


def article_at(root, beat, day):
    d = root / "beats" / beat / "articles"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{day}.json").write_text(json.dumps({"beat": beat, "day": day}))


def test_a_beat_written_today_is_reported_as_published_not_failed(tmp_path):
    article_at(tmp_path, "nm-records", "2026-08-16")
    assert already_published(tmp_path, "nm-records", "2026-08-16") is True


def test_a_beat_with_no_article_today_is_still_to_write(tmp_path):
    assert already_published(tmp_path, "nm-records", "2026-08-16") is False


def test_yesterdays_article_does_not_count_as_todays(tmp_path):
    """The whole point of the beat is that it comes back tomorrow."""
    article_at(tmp_path, "nm-records", "2026-08-15")
    assert already_published(tmp_path, "nm-records", "2026-08-16") is False


def test_an_unknown_beat_is_not_published(tmp_path):
    assert already_published(tmp_path, "never-heard-of-it", "2026-08-16") is False


def test_the_check_does_not_care_about_the_article_being_readable(tmp_path):
    """Immutability keys on the file existing. A corrupt file still blocks the
    write, so it must still count as published here — otherwise the run pays
    for an article it cannot store, which is the bug this exists to prevent."""
    d = tmp_path / "beats" / "b" / "articles"
    d.mkdir(parents=True)
    (d / "2026-08-16.json").write_text("{not json")
    assert already_published(tmp_path, "b", "2026-08-16") is True
