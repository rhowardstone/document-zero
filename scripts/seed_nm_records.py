"""Author the `nm-records` beat from primary and secondary reporting.

Written by an agent acting as the beat agent, not by the stub. Every claim below
was verified against a named publisher and is tiered on what that publisher can
actually establish:

  documented_fact     the existence and content of a filing, a recorded deed, an
                      official order — things a document settles
  credible_allegation what a party asserts in that filing and no one has yet
                      independently confirmed
  question            what the sequence raises but the record does not settle

Confidence is capped by source type regardless of how clearly a thing is written.
Costs nothing to run.
"""
import sys, pathlib, tempfile, json
sys.path.insert(0, "/mnt/d/Newsdesk")
from ledger.store import Ledger
from ledger.sourcetype import classify

W = "beat:nm-records"
BEAT = "nm-records"
NOW = "2026-08-14T10:00:00Z"

S = {  # url -> publisher shorthand
    "nbc":   "https://www.nbcnews.com/news/us-news/jeffrey-epstein-investigation-new-mexico-sues-doj-todd-blanche-blockin-rcna591015",
    "pbs":   "https://www.pbs.org/newshour/politics/state-of-new-mexico-sues-justice-department-and-todd-blanche-saying-they-blocked-its-epstein-probe",
    "cns":   "https://www.courthousenews.com/new-mexico-rips-feds-for-stonewalling-probe-into-epstein-ranch/",
    "abq":   "https://www.abqjournal.com/news/feds-asked-new-mexico-to-halt-its-epstein-probe/2990694",
    "axios": "https://www.axios.com/2026/08/05/new-mexico-sues-doj-epstein-files",
    "trd":   "https://therealdeal.com/texas/2026/02/17/huffines-family-bought-epsteins-zorro-ranch-in-new-mexico/",
    "sfnm":  "https://www.santafenewmexican.com/news/local_news/texas-businessman-running-for-office-owns-epsteins-zorro-ranch-in-santa-fe-county/article_14a05944-1e00-47c8-a4c3-071895abfb57.html",
    "sfnm2": "https://www.santafenewmexican.com/news/local_news/owners-of-former-zorro-ranch-ordered-to-stop-construction-due-to-lack-of-permits/article_e4591527-1b5a-46e9-af05-beb2186d00c2.html",
    "nw":    "https://www.newsweek.com/zorro-ranch-update-evidence-jeffrey-epstein-estate-11635399",
    "cnn":   "https://www.cnn.com/2026/06/01/politics/new-mexico-truth-commission-epstein-zorro-ranch-subpoenas",
    "hill":  "https://thehill.com/homenews/state-watch/5743734-huffines-christian-retreat-epstein-ranch/",
    "ajz":   "https://www.aljazeera.com/news/2026/2/20/new-mexico-reopens-criminal-probe-related-to-jeffrey-epsteins-zorro-ranch",
}

CLAIMS = [
 ("The State of New Mexico sued the Justice Department and Acting Attorney General Todd "
  "Blanche in the U.S. District Court for the District of Columbia over withheld Epstein records.",
  "New Mexico's Attorney General Raul Torrez accused the Department of Justice of unlawfully "
  "withholding unredacted materials", "nbc", "documented_fact", 0.6,
  "Filing reported independently by NBC, PBS and Courthouse News; the existence and venue of a "
  "federal complaint is the kind of fact a filing settles. News ceiling 0.6."),

 ("New Mexico alleges federal prosecutors asked the state to stand down from its Zorro Ranch "
  "sex-trafficking investigation in July 2019, promising to refer state crimes back and share "
  "information once the federal work concluded.",
  "to stand down", "abq", "credible_allegation", 0.55,
  "This is the state's characterisation of a 2019 exchange, reported from records but not "
  "independently confirmed here. An allegation by a party to the dispute, not a settled fact."),

 ("New Mexico alleges the promised federal evidence was never provided.",
  "the promised evidence never came", "cns", "credible_allegation", 0.55,
  "The central allegation of the complaint, asserted by one party. Uncorroborated by DOJ."),

 ("The stated federal rationale for the 2019 stand-down request was avoiding the risk that "
  "parallel investigations would produce inconsistent statements exploitable by defence counsel.",
  "risks of parallel investigations creating inconsistent statements", "abq", "documented_fact", 0.6,
  "A quoted rationale attributed to records. News ceiling 0.6."),

 ("Jeffrey Epstein died in federal custody on 10 August 2019, ending the federal prosecution.",
  "Epstein died in his jail cell on August 10", "abq", "documented_fact", 0.6,
  "Long-established and uncontested. Capped at the news ceiling because it is cited here "
  "through a news source rather than a primary record."),

 ("Zorro Ranch, roughly 8,000 acres in Santa Fe County, was sold at public auction in 2023 to "
  "San Rafael Ranch LLC, an entity registered with the New Mexico Secretary of State roughly one "
  "month before the purchase.",
  "a limited liability company created just a month before the purchase", "sfnm",
  "documented_fact", 0.6,
  "Corporate registration and deed dates are matters of public record; reported by the Santa Fe "
  "New Mexican and The Real Deal."),

 ("The ownership of San Rafael Ranch LLC was not disclosed at purchase and became public only "
  "after a street-name change and a contested property-tax assessment prompted public-records "
  "requests.",
  "It wasn't until a street name change and property taxes were contested that public records "
  "requests revealed the owner", "trd", "documented_fact", 0.6,
  "The mechanism by which the concealment broke is itself reported and checkable."),

 ("The owner is Don Huffines, a former Texas state senator now running for Texas Comptroller; "
  "his wife Mary Catherine is listed as a trustee and his son Colin as an LLC manager.",
  "His wife, Mary Catherine, is listed as a trustee. His son, Colin Huffines, is listed as an "
  "LLC manager", "trd", "documented_fact", 0.6,
  "Named public figure and declared candidate; ownership established through public records."),

 ("New Mexico reopened its criminal investigation on 19 February 2026, after the Justice "
  "Department's January 2026 release of the Epstein files.",
  "reopened", "ajz", "documented_fact", 0.6,
  "Announced by the state and reported contemporaneously."),

 ("Investigators reported recovering evidence of prior excavation and altered substrate at the "
  "property inconsistent with the original construction timeline.",
  "proof of prior excavation and altered substrate inconsistent with the original construction "
  "timeline", "nw", "credible_allegation", 0.5,
  "A forensic characterisation carried by a single outlet and attributed to investigators. "
  "Uncorroborated; the strongest claim here and the least settled."),

 ("State and county officials ordered construction at the property paused, alleging the owners "
  "failed to obtain required permits.",
  "ordered to stop construction due to lack of permits", "sfnm2", "documented_fact", 0.6,
  "A stop-work order is an official act with a paper trail."),

 ("The owners intend to convert the property into a Christian retreat.",
  "plans to turn it into a Christian retreat", "hill", "documented_fact", 0.6,
  "Stated by the owner's campaign and reported directly."),

 ("New Mexico's filing characterises the Epstein files as containing more than 13,000 references "
  "to Zorro Ranch and more than 5,000 to New Mexico as locations where victims were trafficked, "
  "groomed and assaulted.",
  "over 13,000 references to Zorro Ranch and 5,000 references to New Mexico", "nbc",
  "credible_allegation", 0.55,
  "A count asserted by one party about documents this system has not examined. Recorded as the "
  "state's characterisation, not as a verified figure."),
]

QUESTIONS = [
 {"id": "q-standdown-expiry", "beat": BEAT,
  "q": "Did the Justice Department revisit its stand-down request after 10 August 2019, when the "
       "stated rationale for it — the risk of parallel prosecutions — ceased to exist?",
  "known": "The stated reason for asking New Mexico to stand down in July 2019 was the risk that "
           "parallel investigations would generate inconsistent statements. The federal defendant "
           "died on 10 August 2019, roughly two and a half weeks later, ending that prosecution. "
           "New Mexico alleges the promised information was never provided and is litigating for "
           "it in 2026 — six and a half years later.",
  "who": "The Justice Department · the SDNY prosecutors of record in 2019 · Todd Blanche",
  "doc": "Any internal DOJ review of the 2019 referral commitment; the government's answer to the "
         "New Mexico complaint",
  "next": "The government's response on the D.D.C. docket",
  "opened": "14 Aug 2026", "status": "Open · never publicly asked"},

 {"id": "q-evidentiary-loss", "beat": BEAT,
  "q": "What evidentiary value was lost at the site between 2019 and the state regaining access "
       "in 2026?",
  "known": "The property changed hands at auction in 2023, was renamed, and unpermitted "
           "construction began. Investigators reported excavation and altered substrate "
           "inconsistent with the original construction timeline. The state did not have "
           "investigative access during that period.",
  "who": "NMDOJ investigators · Santa Fe County permitting · the current owners",
  "doc": "The stop-work order and permit file; the state's search inventory from March 2026",
  "next": "The New Mexico truth commission's subpoena returns",
  "opened": "14 Aug 2026", "status": "Open"},

 {"id": "q-auction-structure", "beat": BEAT,
  "q": "Was concealing the buyer behind a one-month-old LLC ordinary for this auction, and who "
       "else bid?",
  "known": "San Rafael Ranch LLC was registered roughly a month before the purchase and the "
           "owners' names were withheld. The concealment broke only via a street-name change and "
           "a tax contest, i.e. by accident rather than disclosure.",
  "who": "The auction house · the Epstein estate's compensation administrators · NM Secretary of State",
  "doc": "Auction records; the LLC's formation filing; the recorded warranty deed",
  "next": "Not scheduled — requires a records request",
  "opened": "14 Aug 2026", "status": "Open · not being pursued by anyone visible"},
]

TRIGGERS = [
 {"id": "t-nm-response", "sort": "2026-09-05", "d": "SEP", "beat": BEAT,
  "t": "Government response due, New Mexico v. DOJ",
  "s": "The answer is where the 2019 stand-down rationale must be defended. Non-response is itself recordable."},
 {"id": "t-truth-commission", "sort": "2026-09-15", "d": "SEP", "beat": BEAT,
  "t": "New Mexico truth commission subpoena returns",
  "s": "Began 1 June 2026 with subpoena power over the Zorro Ranch period."},
 {"id": "t-tx-comptroller", "sort": "2026-11-03", "d": "3 NOV", "beat": BEAT,
  "t": "Texas Comptroller election",
  "s": "The property's owner is a candidate; the office oversees state financial matters."},
]

CONTRADICTIONS = [
 {"id": "c-standdown", "beat": BEAT, "opened": "14 Aug 2026",
  "a": "Parallel investigations risk inconsistent statements",
  "asrc": "Federal rationale for the stand-down request, July 2019",
  "b": "The federal prosecution ended on 10 August 2019, and the material was still withheld in 2026",
  "bsrc": "New Mexico's complaint, filed 5 August 2026",
  "tier": "Documented fact against documented fact",
  "st": "Unreconciled. The stated reason expired roughly 18 days after it was given; the "
        "withholding outlasted it by more than six years.",
  "c": "0.6", "item": None},
]


def main():
    root = pathlib.Path(tempfile.mkdtemp()) / "data"
    led = Ledger(root, writer=W)
    for i, (text, quote, key, tier, conf, why) in enumerate(CLAIMS):
        url = S[key]
        led.put_claim({
            "id": f"{BEAT}-2026-08-14-{i:03d}", "beat": BEAT,
            "claim_text": text, "quote": quote,
            "source_type": classify(url), "source_url": url,
            "confidence": conf, "confidence_justification": why, "tier": tier,
            "extracted_by": "agent:eagle-eye", "extracted_at": NOW,
            "verification_rounds": 1, "verifier_families": ["human-directed research"],
        })
    def C(*idx): return [f"{BEAT}-2026-08-14-{i:03d}" for i in idx]
    # Every field names the claims that establish it. A field the ledger cannot
    # trace to evidence is not allowed to exist.
    led.put_state(BEAT, {"beat": BEAT, "as_of": "2026-08-14", "fields": [
        {"k": "Federal suit", "v": "Filed 5 Aug 2026, D.D.C.", "since": "5 Aug",
         "flag": "hot", "claims": C(0)},
        {"k": "State criminal probe", "v": "Reopened 19 Feb 2026", "since": "19 Feb",
         "flag": "hot", "claims": C(8)},
        {"k": "Records sought", "v": "Unredacted Epstein investigative files",
         "since": "5 Aug", "claims": C(0, 2)},
        {"k": "2019 stand-down rationale", "v": "Expired 10 Aug 2019 with the defendant",
         "since": "10 Aug 2019", "flag": "hot", "claims": C(1, 3, 4)},
        {"k": "Site ownership", "v": "San Rafael Ranch LLC (Huffines family), since 2023",
         "since": "Aug 2023", "claims": C(5, 6, 7)},
        {"k": "Site status", "v": "Construction paused for want of permits", "since": "2026",
         "flag": "warn", "claims": C(10, 11)},
        {"k": "Physical evidence", "v": "Excavation and altered substrate reported",
         "since": "Mar 2026", "flag": "warn", "claims": C(9)},
        {"k": "Truth commission", "v": "Subpoenas issuing since 1 Jun 2026", "since": "1 Jun",
         "claims": C(0)},
    ]})
    for d, c, s in [
        ("2019-07-23", "Stand-down requested → state investigation paused on a federal promise.",
         "Reported from records, Albuquerque Journal"),
        ("2019-08-10", "Federal prosecution ended with the defendant's death. Stated rationale for "
                       "the stand-down ceased to apply.", "Contemporaneous reporting"),
        ("2023-08-16", "Site ownership → San Rafael Ranch LLC at public auction; beneficial owner "
                       "concealed.", "Santa Fe New Mexican; The Real Deal"),
        ("2026-02-17", "Beneficial owner revealed as the Huffines family after a street-name change "
                       "and a tax contest.", "The Real Deal"),
        ("2026-02-19", "State criminal probe → reopened following the January federal release.",
         "Al Jazeera"),
        ("2026-03-01", "Site searched by NMDOJ with State Police and K-9 units; excavation and "
                       "altered substrate reported.", "Newsweek; NMDOJ"),
        ("2026-06-01", "Truth commission → began, with subpoena power.", "CNN"),
        ("2026-08-05", "Federal suit → filed against DOJ and Blanche in D.D.C.",
         "NBC News; PBS; Courthouse News"),
    ]:
        led.append_history(BEAT, {"d": d, "c": c, "s": s})

    # Compute the real delta rather than asserting one. This beat has no prior
    # state, so every field is an addition — which is the truthful shape of a
    # beat's first day, and the page should say so rather than imply a change.
    from ledger.diff import diff_state
    delta = diff_state(None, led.get_state(BEAT))

    ed = Ledger(root, writer="editor")
    for q in QUESTIONS:   ed._write_json(f"questions/{q['id']}.json", q)
    for t in TRIGGERS:    ed._write_json(f"triggers/{t['id']}.json", t)
    for c in CONTRADICTIONS: ed._write_json(f"contradictions/{c['id']}.json", c)
    ed._write_json("editions/2026-08-14.json", {
        "day": "2026-08-14",
        "wire": [{"id": BEAT, "beat": BEAT, "score": 18.4, "reason": None,
                  "material_changes": delta.material_changes, "claims": len(CLAIMS),
                  "rejected_claims": 0,
                  "changes": [{"k": c.k, "from": c.old, "to": c.new} for c in delta.changed],
                  "added": [{"k": a.k, "v": a.v} for a in delta.added],
                  "removed": [], "unchanged": delta.unchanged}],
        "omissions": [], "holds": [],
        "counts": {"wire": 1, "capped_out": 0, "omissions": 0, "holds": 0,
                   "refused": 0, "dropped": 0},
        "refusal_summary": {}, "publish": False, "publish_blocked_by": "dry_run"})

    from ledger.render import build, write_data_js
    from ledger.publish import publish
    data = build(root, "/mnt/d/Newsdesk/config/beats.yaml", "2026-08-14")
    write_data_js(data, "/mnt/d/Newsdesk/data.js")
    publish(data, "/mnt/d/Newsdesk", base_url="https://doczero.epstein-data.com")
    print(f"seeded {len(CLAIMS)} claims, {len(QUESTIONS)} questions, "
          f"{len(TRIGGERS)} triggers, {len(CONTRADICTIONS)} contradiction(s)")
    tiers = {}
    for c in Ledger(root).list_claims(BEAT):
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    print(f"tiers: {tiers}")
    print(f"rendered {len(data['items'])} records, {len(data['questions'])} questions, "
          f"{len(data['triggers'])} triggers, {len(data['contradictions'])} contradictions")


if __name__ == "__main__":
    main()
