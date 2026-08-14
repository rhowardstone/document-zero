"""Who is this claim about, and is that person a legitimate subject of scrutiny?

This module exists because two of the three refusal gates take a list of
subjects, and the pipeline was passing them an empty list. A gate that receives
no subjects never fires. The spec said private individuals were protected by
refusal; the running system refused nothing, because nothing ever told it a
private individual was present.

The resolver is deliberately blunt and deliberately biased toward refusal:

  - It finds candidate PERSON names in the claim and its quote.
  - It grants public status only on EVIDENCE of public status — a title in the
    text, a case caption naming them as a party, or an entry in the roster.
  - Everything else is `unknown`, which `Subject.is_public` treats as private.

So the failure mode is over-refusal: an unrecognised public figure gets treated
as private and a wrongdoing claim about them is dropped. That is the direction
this system is supposed to fail in. The cost is a missed story; the cost of the
other direction is a machine publishing an accusation about a private person
with nobody's name on it.

No model, no cost. Heuristics only, so this is auditable and testable line by
line — which matters more here than recall.
"""
from __future__ import annotations
import re

from .refusal import Subject

# ── Titles that establish public status ───────────────────────────────────────
# Holding one of these is the office; scrutiny of the office is the job.
TITLES = (
    r"president", r"vice[- ]president", r"senator", r"sen\.", r"representative",
    r"rep\.", r"congress(?:man|woman|member)", r"governor", r"gov\.", r"mayor",
    r"attorney general", r"solicitor general", r"district attorney",
    r"u\.?s\.? attorney", r"prosecutor", r"judge", r"justice", r"magistrate",
    r"chief justice", r"secretary", r"under ?secretary", r"commissioner",
    r"sheriff", r"chief of police", r"police chief", r"director", r"administrator",
    r"ambassador", r"chairman", r"chairwoman", r"chair", r"comptroller",
    r"treasurer", r"auditor", r"inspector general", r"minister", r"premier",
    r"prime minister", r"speaker", r"whip", r"councilman", r"councilwoman",
    r"council ?member", r"state\s+(?:senator|representative)", r"lt\.? governor",
    r"deputy attorney general", r"assistant attorney general",
)
# Roles that make someone a public figure without being an official.
FIGURE_TITLES = (
    r"chief executive", r"c\.?e\.?o\.?", r"c\.?f\.?o\.?", r"c\.?o\.?o\.?",
    r"executive director", r"founder", r"co-?founder", r"managing partner",
    r"general counsel", r"spokes(?:man|woman|person)", r"press secretary",
    r"billionaire", r"financier", r"chief of staff",
)

# NOTE the lookahead instead of a trailing \b. Several of these titles end in a
# period ("Rep.", "Sen.", "Gov."), and \b does not match between "." and " " —
# both are non-word characters. The effect was silent and serious: a title that
# appeared in the text failed to grant public status, so "Rep. Robert Garcia"
# was treated as a private individual and accountability claims about a sitting
# congressman were refused.
_TITLE_RE = re.compile(
    r"\b(?:" + "|".join(TITLES) + r")(?![a-z])[\s,]*(?:of\s+[A-Z][\w.]*\s+)?", re.I)
_FIGURE_RE = re.compile(r"\b(?:" + "|".join(FIGURE_TITLES) + r")(?![a-z])[\s,]*", re.I)

# ── Things that look like names but are not people ────────────────────────────
ORG_CUES = (
    "inc", "llc", "llp", "ltd", "corp", "corporation", "company", "co",
    "department", "bureau", "agency", "office", "commission", "committee",
    "court", "courts", "university", "college", "institute", "foundation",
    "association", "society", "council", "board", "authority", "administration",
    "service", "services", "bank", "group", "holdings", "partners", "capital",
    "trust", "estate", "fund", "press", "news", "times", "post", "journal",
    "network", "media", "prison", "penitentiary", "jail", "hospital", "school",
    "ranch", "island", "airport", "county", "city", "state", "district",
    "republic", "kingdom", "union", "nations", "states", "party", "senate",
    "house", "congress", "parliament", "assembly", "legislature", "ministry",
    "police", "sheriffs", "attorneys", "prosecutors", "government",
    # Mastheads and scraper furniture. These reached the resolver as "people"
    # ("Add Yahoo", "Trump Yahoo", "Nashville Banner") because an aggregator's
    # chrome ends up inside the scraped title.
    "yahoo", "google", "msn", "banner", "center", "centre", "magazine", "review",
    "gazette", "herald", "tribune", "chronicle", "observer", "standard", "mail",
    "guardian", "telegraph", "wire", "radio", "channel", "digest", "bulletin",
    "daily", "weekly", "today", "insider", "watch", "monitor", "record",
    # Agency and organisation acronyms, admitted as org cues now that ALL-CAPS
    # tokens can form a name candidate.
    "doj", "fbi", "cia", "nsa", "dhs", "ice", "irs", "sec", "epa", "fda", "cdc",
    "atf", "dea", "usdoj", "nmdoj", "sdny", "dnm", "ddc", "usao", "efta", "foia",
    "gao", "omb", "hhs", "dod", "gsa", "nih", "nsf", "faa", "fcc", "ftc", "fema",
    "nato", "un", "eu", "uk", "usa", "ap", "bbc", "cnn", "npr", "pbs", "nbc",
    "abc", "cbs", "msnbc", "wsj", "nyt", "llp", "plc", "gmbh", "spa", "sa",
)
# Common non-name capitalised tokens: calendar words, jurisdictions, connectives.
STOP_TOKENS = frozenset("""
January February March April May June July August September October November
December Monday Tuesday Wednesday Thursday Friday Saturday Sunday
The A An And Or But If When While After Before Since Under Over In On At By For
To From With Without Within Between During Because Although However Federal
State Local National International Public Private Former Current Acting Interim
New Old First Second Third Last Next United States America American Mexico
Texas Florida Virginia York Jersey Hampshire Carolina Dakota Island Columbia
Washington Justice Department Court Supreme District Circuit County City
Epstein-related Records Filing Filed Report Reported Documents Document
According Sources Source Officials Official Investigators Investigation
Prosecutors Attorney General Congress Senate House Committee Subcommittee
Government Administration White House Capitol Congressional Judicial Executive
Legislative Constitution Amendment Act Bill Law Code Rule Order Motion Docket
Case Cases Plaintiff Defendant Appellant Appellee Petitioner Respondent
Republican Republicans Democrat Democrats Democratic GOP Independent Independents
Conservative Conservatives Labour Liberal Rep Sen Gov Reps Sens Govs Mr Mrs Ms Dr
Christmas Thanksgiving Easter Passover Ramadan Hanukkah Eve Day Week Weekend
As Is Was Be Been Being Has Have Had Do Does Did Will Would Can Could May Might
""".split())

_ORG_RE = re.compile(r"\b(?:" + "|".join(ORG_CUES) + r")\b", re.I)

# ── Words that are never part of a person's name ──────────────────────────────
# Headlines are Title Case, so capitalisation carries no signal about proper
# nouns: measured against 1,602 real articles, bare capitalisation read
# "Noncompliance After Hearing" as a person and refused "Trump DOJ Accused of
# Noncompliance" as an accusation against a private individual. That inverts the
# entire principle — it suppressed institutional accountability and protected
# nobody.
#
# This list is function words, headline verbs and process nouns. It deliberately
# EXCLUDES concrete nouns that are common surnames (Baker, Cook, Green, Wood,
# Young, Rich, Bond, Price, Long, House), because dropping those would lose real
# protection for real people.
COMMON = frozenset("""
about above across after again against all also among any are around because
been before being below between both but came come could did does doing done
down during each either else even ever every few for from further had has have
having here how however into its itself just least less like made make many may
might more most much must near need never next nor not now off once only onto
other others our out over own per rather same she should since some such than
that their them then there these they this those though through thus too under
until upon very was way well were what when where whether which while who whom
whose why will with within without would yet you your
accused accuses accusing added admits admitted alleges alleged alleging announce
announced announces answer answers appeal appeals argue argued argues asked asks
attack attacks backs blocked blocks breaks calls charges claims closed comment
comments confirmed confirms continues criticised criticized cuts deal deals
defends demands denied denies details drops ends explains faces facing files
filing finds gets gives goes grants halts hearing hearings hits holds keeps
launches leaves loses makes marks meets moves names offers opens orders passes
pays picks plans pledges points presses probes promises pushes raises reaches
reacts refuses rejects releases reports reveals rules says seeks sees sends
sets shares shows signs slams speaks spent stops takes talks tells testified
testifies threatens told took turns unveils updates urges vows wants warns wins
withdraws works
allegation allegations analysis answer aftermath article background breakdown
briefing case claim comment commentary conclusion coverage decision denial
disclosure discussion dispute document documents effort escalation evidence
exchange explainer fallout finding findings follow gap history impact inquiry
insight interview investigation issue issues latest lawsuit letter list live
look meeting memo mystery news note opinion overview pattern piece plan preview
probe profile progress question questions reaction reason record recording
release remarks reply report response result results review roundup ruling
scandal scrutiny search series session settlement statement story summary
takeaways testimony thread timeline transcript update updates verdict version
view week weekend year years today tomorrow yesterday morning evening night
absolutely actually allegedly apparently basically certainly clearly completely
deeply directly effectively entirely especially essentially eventually exactly
explicitly extremely finally frequently fully generally genuinely gravely
heavily immediately increasingly initially largely likely literally mainly
merely mostly notably obviously openly particularly possibly potentially
previously primarily probably publicly quickly rarely readily recently
reportedly repeatedly seemingly significantly similarly simply slightly
specifically strongly substantially suddenly supposedly totally typically
ultimately unusually usually virtually widely wrongly
alarming appalling awful bizarre brutal chilling controversial crucial damning
dangerous devastating disturbing dramatic egregious explosive extraordinary
horrific incredible insane massive nasty outrageous remarkable reprehensible
scandalous serious shocking staggering startling stunning terrible troubling
unbelievable unprecedented urgent vital
""".split())


def _has_common_token(name: str) -> bool:
    return any(t.strip(".'’-").lower() in COMMON for t in name.split())

# A capitalised token: letters, optional apostrophe/hyphen, or an initial.
# Alternatives are ordered longest-first. The apostrophe branch has to allow an
# EMPTY lowercase run, because "O’Brien" is a capital, no lowercase, then the
# apostrophe — requiring a lowercase letter first dropped the name entirely.
# The uppercase class is À-Þ as well as A-Z, and an ALL-CAPS run of 2+ letters
# counts as a name token. Both were missing, and both erased a person from the
# subject list entirely rather than misclassifying them: "DEBORAH VANCE lied
# about the funds" and "Élodie Martin lied about the funds" each resolved to no
# subject at all, so the private-person gate could not fire.
#
# Admitting ALL-CAPS tokens also admits acronyms, which is why the agency
# acronyms below are org cues. That direction of error only adds refusals.
_U = r"A-ZÀ-ÖØ-Þ"
_L = r"a-zà-öø-ÿ"
_TOK = (rf"(?:[{_U}][{_L}]*(?:['’-][{_U}{_L}][{_L}]*)+"
        rf"|[{_U}][{_L}]+"
        rf"|[{_U}]{{2,}}"
        rf"|[{_U}]\.)")
# A name: 2-4 capitalised tokens, allowing lowercase particles between them.
_NAME_RE = re.compile(
    rf"\b{_TOK}(?:\s+(?:van|von|de|del|della|di|da|du|le|la|bin|al)\s+)?"
    rf"(?:\s+{_TOK}){{1,3}}\b")

# "United States v. Mangione", "Doe v. Roe" — a caption makes someone a party.
_CAPTION_RE = re.compile(
    rf"({_TOK}(?:\s+{_TOK}){{0,3}})\s+v\.?s?\.?\s+({_TOK}(?:\s+{_TOK}){{0,3}})")


def _is_orgish(name: str) -> bool:
    return bool(_ORG_RE.search(name))


def _is_stopword_run(name: str) -> bool:
    """Every token is a calendar word, jurisdiction or connective."""
    toks = [t for t in re.split(r"[\s.]+", name) if t]
    return bool(toks) and all(t in STOP_TOKENS for t in toks)


def candidate_names(text: str) -> list[str]:
    """Spans that could be a person's name. Recall over precision; the caller
    decides status, and an over-inclusive candidate list only means more
    refusals, which is the safe direction."""
    out, seen = [], set()
    for m in _NAME_RE.finditer(text or ""):
        n = m.group(0).strip()
        if _is_orgish(n) or _is_stopword_run(n) or _has_common_token(n):
            continue
        # Drop leading stop tokens, but never below two tokens. Several stop
        # tokens are also given names in this domain — "Bill" is legislation and
        # a first name — and stripping blindly deleted "Bill Richardson" down to
        # a single token, which then failed the two-token rule and vanished. A
        # name the resolver never sees is a gate that never fires.
        toks = n.split()
        while len(toks) > 2 and toks[0] in STOP_TOKENS:
            toks = toks[1:]
        # A surname is never a stopword. "Christmas Democrats" survived every
        # other filter because neither token alone disqualified the pair.
        if len(toks) < 2 or toks[-1] in STOP_TOKENS:
            continue
        n = " ".join(toks)
        if n.lower() in seen:
            continue
        seen.add(n.lower())
        out.append(n)
    return out


def _parties(text: str) -> set[str]:
    """Names appearing as parties in a case caption."""
    who = set()
    for m in _CAPTION_RE.finditer(text or ""):
        for side in m.groups():
            side = side.strip()
            if not _is_orgish(side) and not _is_stopword_run(side):
                who.add(side.lower())
    return who


def _titled(text: str, name: str, pattern: re.Pattern) -> bool:
    """Does a title precede, follow, or begin this name?"""
    # The span itself may open with the title, because "Judge" and "Emmet" and
    # "Sullivan" are all capitalised and the name pattern takes all three. That
    # made a federal judge look private: the code searched the text before the
    # match, where the title no longer was.
    m0 = pattern.match(name)
    if m0 and m0.end() < len(name):
        return True
    for m in re.finditer(re.escape(name), text or ""):
        # Only the CURRENT sentence counts. Scanning a flat 60-character window
        # let a title leak across a full stop: in "CEO Robert Jones spoke today.
        # Alice Smith lied about the charity", the CEO title fell inside Alice
        # Smith's window and made a private individual a public figure, which
        # published an accusation about her.
        before = _sentence_before(text, m.start())
        if pattern.search(before):
            return True
        after = _sentence_after(text, m.end())
        # A title AFTER the name must be an apposition attached to it —
        # "Richardson, the governor, said" — not merely the next clause about
        # somebody else.
        if re.match(r"\s*,\s*(?:the\s+|then[- ])?" + pattern.pattern, after, re.I):
            return True
    return False


_SENT_END = re.compile(r"[.!?][\s\"\u2019\u201d)]|[;\u2014]")

# A period after one of these is an abbreviation, not a sentence end. Without
# this, "Rep. Robert Garcia" splits after "Rep." and the title that establishes
# public status is cut off from the name it belongs to — turning a sitting
# congressman back into a private individual.
_ABBREV = frozenset("""
rep sen gov mr mrs ms dr st jr sr lt gen col adm hon prof atty dept no vs v
u.s us dist ct fed supp cir inc llc ltd co corp
""".split())


def _is_real_boundary(seg: str, m) -> bool:
    if m.group(0)[0] not in ".!?":
        return True                        # ';' and em-dash always split
    before = seg[:m.start()]
    word = re.search(r"([A-Za-z.]+)$", before)
    if not word:
        return True
    w = word.group(1).lower().rstrip(".")
    # A lone capital is an initial: "J. Edgar Hoover".
    return not (w in _ABBREV or len(w) == 1)


def _boundaries(seg: str):
    return [m for m in _SENT_END.finditer(seg) if _is_real_boundary(seg, m)]


def _sentence_before(text: str, idx: int, window: int = 70) -> str:
    """The text just before `idx`, cut at the nearest sentence boundary."""
    seg = text[max(0, idx - window):idx]
    bs = _boundaries(seg)
    return seg[bs[-1].end():] if bs else seg


def _sentence_after(text: str, idx: int, window: int = 70) -> str:
    seg = text[idx:idx + window]
    bs = _boundaries(seg)
    return seg[:bs[0].start()] if bs else seg


_WORD_RE = re.compile(r"[A-Za-zÀ-ɏ]{3,}")


def is_title_case(text: str) -> bool:
    """Does this text capitalise so much that capitalisation means nothing?

    Headlines are Title Case, and in Title Case an initial capital is not
    evidence of a proper noun. Measured on the real corpus, treating headline
    capitalisation as name evidence produced people called "Absolutely
    Reprehensible" and "Nasty As Incumbent Is", and then refused institutional
    accountability claims on their behalf. Where capitalisation carries no
    signal, the resolver requires other evidence instead of inventing a person.
    """
    words = _WORD_RE.findall(text or "")
    # Six words, not four: "Deborah Vance lives at 214 Mercer Street" has five
    # long words of which four are capitalised, and was being read as a headline
    # — which switched off exactly the detection that sentence needs.
    if len(words) < 6:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    return caps / len(words) >= 0.65


def _depossess(name: str) -> str:
    """"Jeffrey Epstein's" -> "Jeffrey Epstein".

    The token pattern allows apostrophes so that O'Brien survives, which meant
    possessives rode along and missed the roster by an exact-match: the most
    frequently named party in the corpus was scored `unknown` nine times purely
    because the source wrote "Epstein's".
    """
    return re.sub(r"['’]s\b", "", name).strip()


def _strip_title(name: str) -> str:
    """"Judge Emmet Sullivan" -> "Emmet Sullivan"; "CEO Robert Jones" -> "Robert Jones".

    The title is evidence about the person, not part of their name. Recording it
    inside the name also breaks roster lookup, which matches on the name.
    """
    for pat in (_TITLE_RE, _FIGURE_RE):
        m = pat.match(name)
        if m and m.end() < len(name):
            rest = name[m.end():].strip(" ,")
            if len(rest.split()) >= 2:
                return rest
    return name


def resolve(claim: dict, roster: dict | None = None) -> list[Subject]:
    """Every person the claim appears to be about, with a status.

    `roster` maps a lowercased name to one of refusal.PUBLIC_STATUSES. It is the
    only way to grant public status to someone the text does not identify by
    office — a curated list, not an inference.
    """
    roster = {k.lower(): v for k, v in (roster or {}).items()}
    # Each field is judged on its own casing: an extractor writes claim_text in
    # sentence case, while a quote may be a verbatim headline. Deciding once for
    # the concatenation would let one headline disable name detection for the
    # whole claim, or let one sentence re-enable it for the headline.
    fields = [str(claim.get(k) or "") for k in ("claim_text", "quote")]
    joined = " ".join(fields)
    parties = _parties(joined)

    seen, subjects = set(), []
    for text in fields:
        titled_text = is_title_case(text)
        for raw in candidate_names(text):
            name = _strip_title(_depossess(raw))
            low = name.lower()
            if low in seen or len(name.split()) < 2:
                continue
            if low in roster:
                status = roster[low]
            elif low in parties:
                # EXACT match only. Substring matching made "Alice Smith" a named
                # party because a caption elsewhere in the text said "Smith v.
                # Jones" — and a bare surname in a caption does not tell you
                # WHICH Smith, so it cannot establish that this person is a party.
                status = "named_party"
            elif _titled(text, raw, _TITLE_RE):
                status = "public_official"
            elif _titled(text, raw, _FIGURE_RE):
                status = "public_figure"
            else:
                # Unknown means private, and private means the gate fires. This
                # branch previously DROPPED the subject when the surrounding text
                # was Title Case, on the theory that headline capitals are not
                # evidence of a proper noun. That was backwards: it meant
                # "Alice Smith: Allegedly Lied About Charity Funds" resolved to
                # no subject at all, so the private-person gate could not fire
                # and the accusation published.
                #
                # Casing is a reason to be UNSURE, and this system resolves
                # uncertainty by refusing. The cost is that a headline fragment
                # can still be mistaken for a person and suppress an
                # institutional story; that error is recoverable and the other
                # one is not.
                status = "unknown"
            seen.add(low)
            subjects.append(Subject(name, status))
    return subjects


def resolver(roster: dict | None = None):
    """A `subject_resolver` callable for BeatAgent."""
    return lambda claim: resolve(claim, roster)
