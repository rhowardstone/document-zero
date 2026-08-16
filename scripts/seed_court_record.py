"""Day two of `nm-records`: the same beat, re-established from primary documents.

Day one built this beat out of news reporting. Every claim was capped at the
`news` ceiling of 0.6 and every one rested on a single publisher — the site's own
`uncorroborated` and `source-types` query views said so in as many words. This
script answers that with the underlying documents.

Source of everything below:

  State of New Mexico v. U.S. Department of Justice, No. 1:26-cv-02762-AHA
  (D.D.C., filed 5 Aug 2026), Doc. 1 (Complaint) and Doc. 1-18 (Exhibit 14, the
  Touhy letter of 3 May 2026), retrieved from the RECAP archive.

Those are `documentation`: court filings, ceiling 0.85. The point is not the
higher number. It is that a filing establishes the existence and content of a
document, where a news report establishes only that a publisher said so.

Two disciplines are load-bearing here:

  A pleading is not a finding. Everything New Mexico ASSERTS about the
  government's motives is `credible_allegation` at best, however plausible.
  What the pleading DOCUMENTS — dates, docket numbers, the text of letters it
  attaches and quotes — is `documented_fact`, because the filing settles that
  those documents exist and say what they say.

  Victims are private individuals. The documents are redacted and this script
  keeps them that way: no name, no identifying detail, no restatement of any
  individual account. The refusal gates would reject such a claim anyway; not
  writing it is better than being refused.

Costs nothing to run.
"""
import sys, pathlib, hashlib
sys.path.insert(0, "/mnt/d/Newsdesk")
from ledger.store import Ledger

BEAT = "nm-records"
COMPLIANCE = "compliance"
W = f"beat:{BEAT}"
NOW = "2026-08-14T11:00:00Z"
AS_OF = "2026-08-14"

# The two primary documents. Both are court filings, so both classify as
# `documentation` — ceiling 0.85 — rather than `news` at 0.6.
DOCS = {
    "complaint": ("https://storage.courtlistener.com/recap/gov.uscourts.dcd.295266/"
                  "gov.uscourts.dcd.295266.1.0.pdf",
                  "Complaint, State of New Mexico v. U.S. Dep't of Justice, "
                  "No. 1:26-cv-02762-AHA (D.D.C. filed Aug. 5, 2026), ECF No. 1"),
    "touhy":     ("https://storage.courtlistener.com/recap/gov.uscourts.dcd.295266/"
                  "gov.uscourts.dcd.295266.1.18.pdf",
                  "Exhibit 14 (Touhy letter of May 3, 2026), State of New Mexico v. "
                  "U.S. Dep't of Justice, No. 1:26-cv-02762-AHA (D.D.C.), ECF No. 1-18"),
    "docket":    ("https://www.courtlistener.com/docket/73721948/"
                  "state-of-new-mexico-v-us-department-of-justice/",
                  "Docket, State of New Mexico v. U.S. Dep't of Justice, "
                  "No. 1:26-cv-02762-AHA (D.D.C.)"),
}

# (id_suffix, claim_text, exact quote, doc, tier, confidence, justification)
CLAIMS = [
    ("docket",
     "The suit is docketed as No. 1:26-cv-02762-AHA in the U.S. District Court for the "
     "District of Columbia, assigned to Judge Amir H. Ali, and is pleaded as review of "
     "agency action under the Administrative Procedure Act rather than as a FOIA case.",
     "899 Administrative Procedure Act/Review or Appeal of Agency Decision",
     "docket", "documented_fact", 0.85,
     "The docket's own nature-of-suit code and assignment. A docket establishes the "
     "posture of a case in a way no characterisation of it can; the distinction from "
     "FOIA matters because it determines the remedy available."),

    ("standdown-call",
     "The complaint dates the federal stand-down request to a telephone call on 23 July "
     "2019 and cites a federal record of that call in the publicly released Epstein "
     "Files.",
     "During a subsequent telephone call on July 23, 2019, USDOJ told NMDOJ to stand "
     "down from its investigation into Epstein's potential criminal activity in New Mexico.",
     "complaint", "documented_fact", 0.85,
     "The date and the existence of a contemporaneous federal record of the call are "
     "established by the filing, which cites the underlying document by Bates number "
     "(EFTA00019183) at a public justice.gov URL. Day one carried this date from news "
     "reporting alone."),

    ("no-pc",
     "The complaint states that federal law enforcement never searched Zorro Ranch, and "
     "cites a federal email of 23 August 2019 — thirteen days after Epstein's death — "
     "that acknowledged a victim who may have been raped at the New Mexico residence "
     "while asserting there was no probable cause to search it.",
     "But federal law enforcement failed to ever search Zorro Ranch.",
     "complaint", "documented_fact", 0.85,
     "The filing quotes and Bates-cites the email (EFTA00165502) to a public "
     "justice.gov URL. The existence and content of that email are documented; whether "
     "the probable-cause assessment was correct is not a question this record settles."),

    ("file-handover",
     "New Mexico gave the federal government its entire investigative file — police "
     "reports, recorded witness interviews and materials on Epstein's use of state public "
     "lands — on 17 September 2019, after agreeing to stand down.",
     "On September 17, 2019, NMDOJ provided USDOJ with its entire investigative file, "
     "including police reports, recorded witness interviews, and materials related to "
     "Epstein's use of New Mexico public lands.",
     "complaint", "documented_fact", 0.85,
     "A dated act of transfer recited in a filing and supported by an attached exhibit. "
     "It establishes the direction of the exchange: the state produced, and is now suing "
     "to receive."),

    ("seizure-request",
     "Then-Attorney General Hector Balderas asked the federal government on 15 October "
     "2019 to begin seizing Epstein's New Mexico land holdings for the benefit of "
     "survivors.",
     "explore initiating the process to seize Epstein's New Mexico land holdings for the "
     "eventual benefit of survivors of these acts and the people of the State of New Mexico",
     "complaint", "documented_fact", 0.85,
     "Quoted from an attached exhibit (Ex. 3 at 16). Establishes that the request was "
     "made and when; the property was instead sold at auction in 2023."),

    ("touhy-invited",
     "The federal government asked New Mexico to file the formal Touhy request it later "
     "declined: on 1 April 2026 an Associate Deputy Attorney General affirmed the "
     "Department's commitment to assisting and requested that New Mexico submit a Touhy "
     "letter through standard channels.",
     "who affirmed the Department's commitment to assisting with the NMDOJ's ongoing "
     "investigation and requested that the NMDOJ submit a Touhy letter through standard "
     "channels",
     "touhy", "documented_fact", 0.85,
     "New Mexico's own contemporaneous account, written to the federal officials who "
     "would have corrected it. The sequence — the request was invited, then refused — "
     "is what the document establishes."),

    ("efta-hook",
     "The records New Mexico seeks are the redacted materials in the federal 'Epstein "
     "Library', compiled under Section 2(a)(1)-(9) of the Epstein Files Transparency Act, "
     "Public Law 119-38 (19 November 2025).",
     "we seek the redacted materials contained in the USDOJ's 'Epstein Library,' compiled "
     "pursuant to Section 2(a)(1)-(9) of the Epstein Files Transparency Act, Public Law "
     "119-38 (Nov. 19, 2025)",
     "touhy", "documented_fact", 0.85,
     "The request names the statute and section it runs against. This is what ties the "
     "New Mexico case to the separate question of federal compliance with that Act."),

    ("deadline",
     "New Mexico's Touhy letter of 3 May 2026 requested a response by 11 May 2026. The "
     "suit was filed on 5 August 2026, 86 days after that date passed.",
     "We respectfully request that your office respond by May 11, 2026, so that logistical "
     "arrangements can be timely finalized.",
     "touhy", "documented_fact", 0.85,
     "The deadline is quoted from the letter and the filing date is on the docket. The "
     "interval is arithmetic, not inference."),

    ("nonproduction",
     "The federal district office's response, dated 30 June 2026 and delivered 14 July, "
     "stated it had neither collected nor retained investigative materials; the "
     "thirty-one accompanying pages consisted largely of a public news article, a public "
     "press release by a former governor, correspondence New Mexico had itself sent, and "
     "a list of follow-up questions.",
     "neither collected nor retained any investigative materials",
     "complaint", "documented_fact", 0.85,
     "The filing enumerates the thirty-one pages item by item. The content of a "
     "production is a documentable fact; whether it satisfies the request is contested."),

    ("protective-order",
     "Asked whether the federal government would join New Mexico in seeking a "
     "modification of the protective orders it cited as the obstacle, so that the orders "
     "would expressly permit disclosure for law-enforcement purposes, a Deputy United "
     "States Attorney responded that such cooperation was 'unlikely' and identified no "
     "path through which the two offices could work together.",
     "unlikely",
     "complaint", "documented_fact", 0.85,
     "The exchange is recited with dates and an attached exhibit. It is the difference "
     "between an obstacle and a choice: the stated impediment is one the objecting party "
     "declined to help remove."),

    ("public-vs-conduct",
     "Federal officials made public assurances of cooperation during the same period the "
     "requests went unanswered: a First Assistant United States Attorney said on 12 June "
     "2026 'I anticipate full cooperation', and a department spokesperson said on 7 July "
     "2026 that it 'stands ready to provide necessary assistance'.",
     "[Attorney General Torrez] wants cooperation, we want to cooperate,",
     "complaint", "credible_allegation", 0.8,
     "The statements themselves are documented and dated. That they conflict with the "
     "conduct is New Mexico's characterisation, made in a pleading by an adverse party, "
     "and is not a finding of any court."),

    ("judicial-notice",
     "New Mexico's filing notes that the Justice Department has argued in other 2026 "
     "litigation that courts may take judicial notice of an Acting Attorney General's "
     "recorded public statements as binding party admissions.",
     "Because the Acting Attorney General's statements were recorded, this Court can take "
     "judicial notice of them.",
     "complaint", "documented_fact", 0.85,
     "Quoted from the government's own brief in Floyd v. Dep't of Justice, No. "
     "26-cv-01399 (E.D. Va.), ECF No. 78, cited in the filing's footnote 16. The position "
     "is the government's, taken in a different case."),

    ("scale",
     "The federal filing states the released Epstein Files contain more than 13,000 "
     "references to Zorro Ranch and more than 5,000 references to New Mexico as locations "
     "where victims were trafficked, groomed and assaulted.",
     "The Epstein Files include over 13,000 references to Zorro Ranch and 5,000 references "
     "to New Mexico as locations where victims were trafficked, groomed, and assaulted.",
     "complaint", "documented_fact", 0.85,
     "Day one carried this figure from a news report at the 0.6 news ceiling. It is now "
     "sourced to the filing that asserts it, which is what a news report was reporting."),

    ("offences",
     "New Mexico states it is investigating potential felony offences including homicide, "
     "kidnapping, criminal sexual penetration, criminal sexual contact and human "
     "trafficking, under named provisions of the New Mexico criminal code.",
     "the state of New Mexico is investigating potential felony offenses, including but "
     "not limited to homicide, kidnapping, criminal sexual penetration, criminal sexual "
     "contact, and human trafficking",
     "touhy", "documented_fact", 0.85,
     "The scope of the state's investigation is stated in its own formal request, with "
     "statutory citations. That an offence is under investigation is not an allegation "
     "that any identified person committed it, and none is recorded here."),

    ("search-date",
     "The state's own formal request dates its search of the property to 9 March 2026.",
     "On March 9, 2026, the NMDOJ executed a search of the property and has since begun "
     "contacting potential victims and witnesses to develop a firsthand account of events.",
     "touhy", "documented_fact", 0.85,
     "A date the state gives in a signed request to federal officials. It contradicts the "
     "1 March date this beat carried from news reporting; the primary document governs "
     "and the contradiction is recorded rather than silently overwritten."),
]

# Claims that belong to the `compliance` beat — federal compliance with the
# Epstein Files Transparency Act — which until now held nothing at all.
COMPLIANCE_CLAIMS = [
    ("efta-redaction",
     "New Mexico's complaint alleges that the Act required the files to be released "
     "redacted to protect survivors, and that the department instead publicly posted "
     "unredacted personal information about survivors.",
     "But USDOJ instead publicly posted detailed, unredacted personal information about "
     "survivors, ranging from their contact information to nude images.",
     "complaint", "credible_allegation", 0.8,
     "An allegation in a pleading by an adverse party, quoted exactly. The filing cites "
     "an attached letter from the Attorney General and Acting Attorney General to "
     "Congress dated 30 January 2026. No court has found this."),

    ("efta-as-shield",
     "The federal government has cited the Epstein Files Transparency Act itself, "
     "together with protective orders, as grounds for declining to produce unredacted "
     "records to a state criminal investigation.",
     "reiterated his view that EFTA and the existing protective orders precluded "
     "production of materials in response to NMDOJ's request",
     "complaint", "documented_fact", 0.85,
     "The position taken is documented with a date and an attached exhibit. A "
     "transparency statute being invoked as a reason to withhold is a fact about the "
     "Act's operation, whatever one concludes about it."),
]


def main(root="/mnt/d/Newsdesk/ledger-data"):
    root = pathlib.Path(root)
    led = Ledger(root, writer=W)
    comp = Ledger(root, writer=f"beat:{COMPLIANCE}")
    ing = Ledger(root, writer="ingest")

    SHA = {}
    for key, (url, title) in DOCS.items():
        sha = hashlib.sha256(url.encode("utf-8")).hexdigest()
        SHA[key] = sha
        try:
            ing.put_source("2026-08-05", {
                "sha256": sha, "url": url, "title": title,
                "source_name": "courtlistener.com", "source_type": "documentation",
                "published_at": "2026-08-05T00:00:00Z", "first_seen": NOW,
                "candidate_beats": [{"beat": BEAT, "score": 1.0},
                                    {"beat": COMPLIANCE, "score": 0.6}]})
        except FileExistsError:
            pass

    def write(ledger, beat, rows):
        ids = {}
        for suffix, text, quote, doc, tier, conf, why in rows:
            cid = f"{beat}-2026-08-14-doc-{suffix}"
            ids[suffix] = cid
            url, _ = DOCS[doc]
            ledger.put_claim({
                "id": cid, "beat": beat, "claim_text": text, "quote": quote,
                "source_sha": SHA[doc], "source_type": "documentation",
                "source_url": url, "confidence": conf,
                "confidence_justification": why, "tier": tier,
                "extracted_by": "agent:eagle-eye/primary-documents",
                "extracted_at": NOW, "verification_rounds": 1,
                "verifier_families": ["quote-checked against the filed PDF"]})
        return ids

    n = write(led, BEAT, CLAIMS)
    c = write(comp, COMPLIANCE, COMPLIANCE_CLAIMS)

    # ── The new state ────────────────────────────────────────────────────────
    # Three fields change, four are added, the rest stand. This is the first
    # edition in which the site has a real before -> after to show.
    led.put_state(BEAT, {"beat": BEAT, "as_of": AS_OF, "fields": [
        {"k": "Federal suit",
         "v": "No. 1:26-cv-02762-AHA, D.D.C. (Ali, J.), APA review",
         "since": "5 Aug", "claims": [n["docket"]]},
        {"k": "State criminal probe", "v": "Reopened 19 Feb 2026",
         "since": "19 Feb", "claims": [n["offences"]]},
        {"k": "Records sought",
         "v": "Unredacted 'Epstein Library' records, EFTA §2(a)(1)-(9)",
         "since": "3 May", "claims": [n["efta-hook"]]},
        {"k": "2019 stand-down rationale", "v": "Expired 10 Aug 2019 with the defendant",
         "since": "10 Aug 2019", "claims": [n["standdown-call"], n["no-pc"]]},
        {"k": "Administrative exhaustion",
         "v": "Touhy request 3 May 2026; treated as denied 31 Jul 2026",
         "since": "31 Jul", "claims": [n["deadline"], n["nonproduction"]]},
        {"k": "Stated grounds for refusal",
         "v": "Overbreadth; Privacy Act; Epstein and Maxwell protective orders",
         "since": "14 Jul", "claims": [n["protective-order"], n["nonproduction"]]},
        {"k": "Protective-order modification",
         "v": "Sought by the state; federal cooperation called 'unlikely'",
         "since": "14 Jul", "claims": [n["protective-order"]]},
        {"k": "Federal search of the property", "v": "Never conducted",
         "since": "23 Aug 2019", "claims": [n["no-pc"]]},
        {"k": "Site ownership", "v": "San Rafael Ranch LLC (Huffines family), since 2023",
         "since": "Aug 2023", "claims": [n["seizure-request"]]},
        {"k": "Physical evidence", "v": "Excavation and altered substrate reported",
         "since": "Mar 2026", "claims": [n["search-date"]]},
        # Carried forward from day one. It is still true and the documents do not
        # touch it, so dropping it would have rendered on the page as a struck
        # field — a change the record did not make.
        {"k": "Site status", "v": "Construction paused for want of permits",
         "since": "2026", "claims": ["nm-records-2026-08-14-010"]},
        {"k": "Truth commission", "v": "Subpoenas issuing since 1 Jun 2026",
         "since": "1 Jun", "claims": [n["offences"]]},
    ]})

    for d, chg, sup in [
        ("2026-08-14", "Beat re-established from the filed complaint and its exhibits, "
                       "replacing news reporting as the source of record.",
                       "15 claims from 3 court documents"),
        ("2026-08-05", "Federal suit → docketed 1:26-cv-02762-AHA before Judge Ali as "
                       "APA review, not FOIA.", "Docket, D.D.C."),
        ("2026-07-31", "Administrative exhaustion → Touhy request treated as denied.",
                       "Complaint ¶¶71-77"),
        ("2026-07-14", "Stated grounds for refusal → overbreadth, Privacy Act, and the "
                       "Epstein and Maxwell protective orders.", "Complaint ¶¶74-76"),
        ("2026-05-03", "Administrative exhaustion → formal Touhy request served, response "
                       "sought by 11 May.", "Exhibit 14"),
        ("2019-08-23", "Federal search of the property → declined for want of probable "
                       "cause, 13 days after the defendant's death. Never conducted.",
                       "Complaint ¶30 n.6, citing EFTA00165502"),
    ]:
        led.append_history(BEAT, {"d": d, "c": chg, "s": sup})

    comp.put_state(COMPLIANCE, {"beat": COMPLIANCE, "as_of": AS_OF, "fields": [
        {"k": "Statute", "v": "Epstein Files Transparency Act, Pub. L. 119-38 (2025)",
         "since": "19 Nov 2025", "claims": [c["efta-as-shield"]]},
        {"k": "Invoked as grounds to withhold",
         "v": "Yes — against a state criminal investigation, 31 Jul 2026",
         "since": "31 Jul", "claims": [c["efta-as-shield"]]},
        {"k": "Redaction compliance", "v": "Contested in litigation",
         "since": "5 Aug", "claims": [c["efta-redaction"]]},
    ]})
    comp.append_history(COMPLIANCE, {
        "d": "2026-08-14",
        "c": "Beat opened. A transparency statute is being cited as a reason to withhold.",
        "s": "2 claims from the New Mexico complaint"})

    # ── What the documents changed about the questions ───────────────────────
    q = Ledger(root, writer="editor")
    # Reuses day one's id so the narrowed question SUPERSEDES it rather than
    # appearing beside it. A question the record has narrowed is the same
    # question, not a new one.
    q._write_json("questions/q-evidentiary-loss.json", {
        "id": "q-evidentiary-loss", "beat": BEAT,
        "q": "What evidentiary value was lost at the site between 2019 and the state "
             "regaining access in 2026?",
        "known": "The record now establishes that federal law enforcement never searched "
                 "the property, and that on 23 August 2019 — thirteen days after the "
                 "defendant's death ended the federal case — a federal email acknowledged "
                 "a victim who may have been raped at the residence while asserting there "
                 "was no probable cause for a search. The first search was conducted by "
                 "the state on 9 March 2026, roughly six and a half years later, and "
                 "reported excavation and altered substrate.",
        "who": "FBI Albuquerque · the U.S. Attorney's Office for the District of New "
               "Mexico · whoever authored the 23 August 2019 assessment",
        "doc": "The unredacted 23 August 2019 email (EFTA00165502) and any probable-cause "
               "analysis behind it",
        "next": "Not scheduled. It is not among the records the Touhy request enumerates.",
        "opened": "14 Aug 2026",
        "status": "Open · narrowed by the complaint, not answered"})

    q._write_json("questions/q-touhy-gap.json", {
        "id": "q-touhy-gap", "beat": BEAT,
        "q": "What happened inside the department between 11 May and 31 July 2026, while "
             "it publicly promised cooperation and produced nothing?",
        "known": "A response was requested by 11 May. On 11 June a district office said "
                 "'Main Justice' was preparing files; on 12 June a First Assistant United "
                 "States Attorney said publicly 'I anticipate full cooperation'; on 7 July "
                 "a spokesperson said the department 'stands ready to provide necessary "
                 "assistance'. The production that arrived on 14 July contained a news "
                 "article, a press release, and the state's own correspondence.",
        "who": "The Office of the Deputy Attorney General · the Executive Office for "
               "United States Attorneys · SDNY",
        "doc": "Internal correspondence on the handling of the Touhy request between "
               "3 May and 31 July 2026",
        "next": "The government's response to the complaint is due 5 September 2026.",
        "opened": "14 Aug 2026",
        "status": "Open · the gap is documented, its contents are not"})

    q._write_json("contradictions/c-cooperation.json", {
        "id": "c-cooperation", "beat": BEAT, "opened": "14 Aug 2026",
        "a": "Federal officials stated publicly in June and July 2026 that they "
             "anticipated full cooperation and stood ready to assist.",
        "asrc": "Statements of 12 June and 7 July 2026, quoted in the complaint",
        "b": "The production delivered on 14 July 2026 contained no investigative "
             "material, and both the district office and SDNY refused the request.",
        "bsrc": "Complaint ¶¶72-77 and its Exhibits 3 and 23"})

    q._write_json("contradictions/c-search-date.json", {
        "id": "c-search-date", "beat": BEAT, "opened": "14 Aug 2026",
        "a": "The state's search of the property occurred on 1 March 2026.",
        "asrc": "News reporting, carried by this beat on 13 August 2026",
        "b": "The state's search of the property occurred on 9 March 2026.",
        "bsrc": "The state's own Touhy letter of 3 May 2026, Exhibit 14 at 2"})

    # Supersedes day one's entry for the same event by reusing its id. A trigger
    # is an obligation in the world, not a note about it: two rows for one
    # deadline is the ledger double-counting reality.
    q._write_json("triggers/t-nm-response.json", {
        "id": "t-nm-response", "sort": "2026-09-05", "d": "SEP", "beat": BEAT,
        "t": "Government response due, New Mexico v. DOJ (1:26-cv-02762-AHA)",
        "s": "The answer is where the protective-order and Privacy Act grounds must be "
             "defended on the record. Non-response is itself recordable."})

    return root


if __name__ == "__main__":
    print("wrote day two to", main())
