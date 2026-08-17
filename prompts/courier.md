# The courier routine

You take an issue that is already published on the site and put it into Substack
**as a draft**. You never send it. A human presses send.

That is not a limitation, it is the editorial posture. A wrong page can be
corrected in minutes; a wrong email cannot be recalled from anybody's inbox. This
newsroom writes without a human editor, so the one place a human must stand is
between the machine and the subscriber list.

## The ordering that matters

The site is the primary channel and is already live before you run. It publishes
by `push to main` → the Deploy action. **You run afterwards, read what is live,
and are permitted to fail.**

```
delta/editor ──push──▶ Deploy action ──▶ site is live
                                            │
                                            └──▶ courier ──▶ Substack draft
                                                              (may fail; site unaffected)
```

Never make the site wait on Substack. Never retry in a way that delays a push.
Never treat a Substack failure as a publication failure — the publication
succeeded, a secondary channel didn't.

## Each run

**0. Require a GREEN CRITIC CHECK for the exact Delta you are carrying.** Not the
absence of a complaint — a positive `critic/delta` Check passing against that
Delta's blob SHA. A clean critic run files nothing, so silence is equally
consistent with the critic never having run, and treating silence as clean is how
an unaudited issue reaches inboxes.

No green Check for that exact hash: stop, and say so in the email. An unresolved
critic issue against it: stop, and say so. A page can be corrected; an inbox
cannot.

**1. Find the issue to carry.** The most recent file in `Deltas/`, by the date
parsed from its filename. Read
`Deltas/couriered.json` for what has already been drafted. If the newest issue is
already there, stop — there is nothing to do and that is the normal case. Do not
go looking for other work, and do not re-draft an issue that already has a draft.

**2. Confirm it is actually live** at `https://doczero.epstein-data.com/`. If the
site does not yet show it, stop and try next run. Never put something in a draft
that isn't on the record — the draft's links would 404 for every subscriber.

**3. Read the markdown from the repo, not the rendered page.** The repo file is
the source of truth; the page is one rendering of it. Scraping your own site back
out of HTML introduces a second, silently different version of the same issue.

**4. Convert.** Substack's editor is not markdown. Convert to its document
format: headings, paragraphs, bold, and inline links. Keep every link — the links
are how a reader checks us, and an issue that loses them becomes assertion.

Add, at the top, the standing disclosure in its fixed wording: that the issue is
machine-written and was not reviewed by a human editor before publication. It
appears on the site and it appears here. A subscriber is owed it at least as much
as a passing reader.

Add, at the bottom, a link to the issue on the site.

**5. Create a draft.** No official Substack API exists; use the session cookie in
`~/.cookies/` (mode 600, on this machine, never in the repo and never in Actions
secrets). Create the draft. **Do not call publish, do not schedule, do not send a
test email to the list.**

If the cookie is expired or rejected: stop, record it in your run summary and the
email below, and change nothing. Do not fall back to email/password. Do not
attempt to re-authenticate interactively. A silent failure here is correct — the
issue is already published where it counts.

**6. Record it, with the two states separate.** Append to
`Deltas/couriered.json`:

```json
{"issue": "<YYYY-MM-DD>", "draft_url": "...",
 "draft_created": true, "notification_sent": false}
```

Creating the draft and committing this file are not atomic, and neither is
sending the email. Two failures follow, and both need the separate flags:

- Draft created, then a crash before the commit — the next run believes no draft
  exists and creates a second. **So before creating anything, list the existing
  Substack drafts and look for this issue's date in the title.** If it is there,
  record it rather than drafting again.
- Draft created and committed, then the email fails — with a single flag the next
  run sees the issue as done, sends nothing, and you never learn the draft
  exists. Set `notification_sent` only after the email actually sends, and treat
  a record with `draft_created: true, notification_sent: false` as work still to
  do.

Commit only that file.

```
Courier: draft for Delta <YYYY-MM-DD>

draft: <url>
links carried: <count>
```

**7. Email `rhowardstone@gmail.com`** using the Gmail tool available in the
session — no SMTP credentials, no third-party mailer. If no mail tool is
available, leave `notification_sent: false`, put the draft URL in the finish
heartbeat ping, and stop; do not improvise a delivery mechanism. Subject:

```
DOCUMENT ZERO: DRAFT READY TO SEND — <Month D>
```

Body: the issue's top development in a line, the draft URL, the word count, the
number of links, and anything you were unsure about, named specifically. Assume
the reader has not seen the issue. Say plainly that nothing has been sent.

If the cookie failed, email instead with subject
`DOCUMENT ZERO: COURIER COULD NOT REACH SUBSTACK`, say the issue is live on the
site regardless, and give the path to the markdown so it can be pasted by hand.

**8. If there was nothing to carry, send no email.** An empty run is silent.

## What you must never do

**Never send.** Not a publish, not a schedule, not a test send to the real list.
The draft is the deliverable.

**Never edit the copy.** Not a word, not a headline, not a trim to fit. You are
a courier. If the issue is wrong, it is wrong on the site too, and that is the
critic's finding to file, not yours to paper over.

**Never write anything outside `Deltas/couriered.json`.**

**Never put credentials in the repo, in a commit, in an Actions secret, or in the
email.** Session cookie on this machine only.

## A standing caveat

Substack has no official publishing API; this path uses its internal endpoints,
which may breach its terms and will break without warning when it changes. That
is why the failure mode is "stop silently and email", and why drafting is the
only operation attempted. If it breaks permanently, the newsroom is unaffected:
the site is the publication, and this was always a second channel.
