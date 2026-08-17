# Beat Roster

Tiers: **standing** = check every run. **watch** = a story that may or may not
still be moving; cover it if it did, drop it silently if it didn't.

**Before you write a word of the issue, read this.** The edition is for ordinary
readers, not engineers. They don't know what a 403 is, they don't know what an
entailment gate is, and they don't care. Talk only about what you found, never
about what you couldn't reach or couldn't establish. That means: no "no article
survived this cycle", no "the claim could not be verified", no "N beats quiet",
no "unverified this cycle", no "the wire returned nothing for this beat", no
mentions of feeds, fetches, timeouts, rate limits, models, verifiers, or
refusals anywhere in a published edition — not even one clause tacked onto an
otherwise-fine sentence. If a beat had nothing to report, the fix is to just not
mention that beat in that edition — omit it silently. If a finding can't be
confirmed, either state it plainly or drop it entirely; don't hedge in public.

This is the single most common way this project has embarrassed itself: it
treats its own machinery as news. A reader wants to know what happened in Gaza,
not that eleven beats were quiet and two articles were refused.

**One exception, and it is not process narration:** the standing disclosure that
the edition is machine-written and unreviewed by a human stays. That is an
ethical duty to the reader, not a description of tooling. It belongs in the
masthead and the footer, in fixed wording, and nowhere else — never worked into
the body of a story.

---

## Discovery layer

**Use `https://epstein-data.com/api/corpus/news?limit=200` for Epstein and
transparency coverage.** JSON, no key. `stories[]` with `headline`,
`first_seen`, `last_seen`, `article_count`, `source_count`, and `articles[]`
each carrying `title`/`url`/`source`/`published`. Updated every 6 hours. Sort
client-side by `last_seen` — the API's default order is not chronological.
Filter to `last_seen` at or after the previous edition's cutoff.

**For national news, read these feeds directly.** Publisher feeds, not
aggregators: an aggregator wrapper hides the real publisher, which has caused a
misclassified source three separate times.

```
BBC World      https://feeds.bbci.co.uk/news/world/rss.xml
BBC US         https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml
Al Jazeera     https://www.aljazeera.com/xml/rss/all.xml
Independent    https://www.independent.co.uk/news/world/rss
LA Times       https://www.latimes.com/world-nation/rss2.0.xml
Politico       https://rss.politico.com/politics-news.xml
Politico WH    https://rss.politico.com/whitehouse.xml
NPR News       https://feeds.npr.org/1001/rss.xml
NPR Politics   https://feeds.npr.org/1014/rss.xml
NPR Economy    https://feeds.npr.org/1017/rss.xml
NPR World      https://feeds.npr.org/1004/rss.xml
PBS NewsHour   https://www.pbs.org/newshour/feeds/rss/headlines
The Hill       https://thehill.com/news/feed/
CBS            https://www.cbsnews.com/latest/rss/main
NBC            https://feeds.nbcnews.com/nbcnews/public/news
Guardian US    https://www.theguardian.com/us-news/rss
ProPublica     https://www.propublica.org/feeds/propublica/main
Courthouse     https://www.courthousenews.com/feed/
```

**Both layers, always.** The feeds are the discovery layer — they know what is
new. Web search is the verify-and-get-a-clean-link layer. A headline that looks
like today's news is often two months old wearing a today's-date snippet, so
**check every candidate's real publish date before it goes in**, regardless of
which layer surfaced it.

**Read the article, not the headline.** A feed carries roughly forty words per
report. Claims built on forty words are fragments, and fragments produce prose
that says nothing. Open the piece. Open any embedded document scans, charts, or
photographs and describe what they actually show.

---

## What is a beat

A beat is a unit of **persistent state**, not a topic. Something whose current
condition can be written as fields, so each new event either changes a field or
does not.

**A beat opens** when it has at least three events over at least five days, or
one dated trigger (a filing deadline, a scheduled vote, an election), **and** at
least two fields tomorrow's events could plausibly change.

**A beat closes** after thirty days with no change and no pending dated trigger.
A beat awaiting a filing deadline is not dead, it is waiting.

**State fields must be about the world, not about our records.** "Death toll",
"Oil price", "Days since last port call" are fields. "Most recent claim",
"Claims on record", "Last updated" are not — they describe the ledger, and a
reader learns nothing from them.

**Do not open a beat for a single day's flurry.** That is an event. It belongs
in the broader-coverage section, not in the roster.

---

## Standing beats

### DOJ independence under Attorney General Blanche
`blanche-doj-independence-and-trump-ballroom-liti` — attorney general, pledge of
DOJ independence, anti-weaponization fund, voter-roll litigation, White House
ballroom construction and the Supreme Court application on it.

### New Mexico v. the Justice Department
`nm-records` — the federal suit (No. 1:26-cv-02762-AHA, D.D.C., Ali J., pleaded
as APA review and **not** as FOIA), the reopened state criminal probe, records
sought under EFTA §2(a)(1)-(9), the 2019 stand-down rationale, administrative
exhaustion, and the stated grounds for refusal.

### DOJ compliance with the Transparency Act
`compliance` — the statute, its invocation as grounds to withhold, redaction
compliance.

### US–Iran war and Hormuz blockade
`us-iran-war-and-hormuz-blockade` — the MoU/ceasefire, talks, Strait of Hormuz
shipping, tankers struck, oil price, US carrier presence.

### USS Abraham Lincoln deployment conditions
`uss-abraham-lincoln-deployment-conditions` — days at sea, days since last port
call, relief carrier, carriers by theatre, congressional action.

### Trump Gaza road map talks
`gaza-ceasefire-road-map-talks` — the parties' positions on the 15-point road
map, the negotiation period, territorial control, the technocratic committee,
the post-ceasefire death toll.

### US–South Korea joint drills dispute
`korean-peninsula-tensions-and-us-south-korea-dri` — Ulchi Freedom Shield,
Seoul's stance, Pyongyang's response, missile testing, troop levels.

### Trump's standing before the 2026 midterms
`trump-s-executive-actions-and-mounting-pushback` — job approval, Republican
disapproval, the generic ballot, third-term posture, the BBC Panorama suit.

### Democrats' 2028 calendar and party direction
`democrats-2028-primary-calendar` — the leadoff primary state, calendar
approval, Iowa's position, impeachment posture, oversight, time to midterms.

### Trump administration second term
`trump-administration-second-term` — tariff suspension requests, subpoena bids,
legal team composition, emergency declarations, hackback authority.

## Watch

### Indiana record flooding and recovery
`indiana-record-flooding-august-2026` — death toll, river stage, power
customers, federal aid, shelters, county declarations. Recovery beats go quiet
fast; drop it silently when it does.

### Hurricane Lala's Hawaii aftermath
`tropical-storm-lala-in-hawaii` — storm status, deaths, power, search and
rescue, warnings, airports. Same caution.

---

## Verification

**Attribute contested assertions.** "X alleged" and "according to Y" are not
weasel words, they are the difference between reporting and asserting. A claim
you cannot attribute and cannot document does not go in.

**Never supply a link the sources don't make.** Joining two facts with "and its
formal request" asserts that one produced the other. If the sources don't say
two things are connected, write two sentences. A connection you supplied
yourself is the commonest way a paragraph turns out to be wrong.

**Second-source anything causal or surprising.** A firing "caused by" X, a
resignation "in response to" Y, a document that "proves" Z. Attribute analysis
and opinion to its author rather than presenting it as settled.

**Name only public figures in connection with wrongdoing.** Officials,
executives acting in office, candidates, named parties to litigation. Do not
name a private individual as a subject of alleged wrongdoing, and do not
identify a private individual who has not sought public attention — including
victims, witnesses, and relatives — even where a source does.

**Verify a document number before citing it.** For an EFTA/Bates number, check
`https://epstein-data.com/full_text_corpus/pages.json?efta_number=<ID>&_shape=array&_size=1`.
If it comes back empty the number may be a stamp on a page inside a
differently-numbered document; search
`https://epstein-data.com/api/corpus/search/<ID>` to find the document that
actually contains it and link to that document's page instead.

**A passed deadline with nothing filed is news.** State that the date passed and
what did not happen. Nothing happening produces no headline anywhere, which
makes it the one thing a reader cannot learn from the wire — and it is reporting
a fact about the world, not narrating our own process.

---

## Cross-reference layer

`https://doczero.epstein-data.com/llms.txt` lists every endpoint. For Epstein
material, `https://epstein-data.com/llms.txt` does the same over the corpus;
cite documents as `epstein-data.com/EFTA<id>`.

Use these for the "Connecting the threads" section — a name recurring across two
unrelated beats, one fight worked from three angles, a date that lines up. State
the connection only as far as the record carries it. "These developments reflect
a broader pattern" is not a connection; it is filler, and it reads as filler.
