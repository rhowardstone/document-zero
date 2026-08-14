/* ============================================================
   DOCUMENT ZERO — data layer
   This is the shape the SQLite tables render into. Every view in
   the site is a query over this object.
   ============================================================ */
window.DZ = {

edition:{n:'001', date:'14 August 2026', updated:'06:00 ET', next:'15 August'},

/* ---------- DOSSIERS — permanent umbrellas, never close ---------- */
dossiers:[
 {id:'iran',    name:'The Iran War'},
 {id:'econ',    name:'Household Costs & the Fed'},
 {id:'power',   name:'Executive Power & the Courts'},
 {id:'records', name:'The Epstein Records'},
 {id:'immig',   name:'Immigration Enforcement'},
 {id:'account', name:'Race, Policing & Accountability'},
 {id:'surv',    name:'Surveillance & Civil Liberties'},
 {id:'violence',name:'Political Violence'},
 {id:'health',  name:'Public Health'},
 {id:'elect',   name:'Elections & Representation'},
 {id:'energy',  name:'Energy, Land & Infrastructure'},
 {id:'disaster',name:'Weather & Disaster Response'}
],

/* ---------- TYPES — cross-cutting filters, not groupings ---------- */
types:[
 {id:'case',    name:'Legal case'},
 {id:'reg',     name:'Regulation'},
 {id:'oversight',name:'Oversight & compliance'},
 {id:'conflict',name:'Armed conflict'},
 {id:'market',  name:'Markets & prices'},
 {id:'inst',    name:'Institutions'},
 {id:'death',   name:'Death investigation'},
 {id:'tech',    name:'Technology & data'},
 {id:'event',   name:'Disaster & event'}
],

/* ---------- BEATS — state objects ----------
   status: moved | recirculating | unresolved | quiet | receding | closing
   state:  the fields. THIS is what makes it a beat.
   history: revisions, newest first.
------------------------------------------------------------------ */
beats:[
{id:'hormuz', name:'The Strait of Hormuz & the blockade', dossiers:['iran','energy'], types:['conflict','market'],
 status:'moved', opened:'7 April 2026', lastChange:'14 August 2026', events:214,
 summary:'American naval blockade of Iranian ports, Iranian interference with commercial transit, and the agreements that have governed both.',
 state:[
  {k:'Blockade',        v:'In force',                  since:'early Aug', flag:'hot'},
  {k:'Transit volume',  v:'Near standstill',           since:'14 Aug',    flag:'hot'},
  {k:'Governing agreement', v:'MOU of 17 Jun — expires 16 Aug', since:'17 Jun', flag:'warn'},
  {k:'Attacks on shipping (24h)', v:'2',               since:'14 Aug',    flag:'hot'},
  {k:'Ceasefire',       v:'Holding on major combat',   since:'7 Apr',     flag:'ok'},
  {k:'Stated US posture', v:'Maintainable indefinitely', since:'14 Aug',  flag:''}],
 history:[
  {d:'14 Aug', c:'Transit → near standstill. Attacks +2. US posture stated as indefinite.', s:'Hegseth remarks; Times of Israel liveblog'},
  {d:'early Aug', c:'Blockade → reimposed, after renewed attacks on shipping and on several Arab states.', s:'Wire reporting'},
  {d:'17 Jun', c:'Governing agreement → MOU. Blockade declared removed; safe passage for 60 days only.', s:'Trump–Pezeshkian memorandum'},
  {d:'7 Apr',  c:'Beat opened. Ceasefire halts major combat operations.', s:'Ceasefire announcement'}],
 unknown:['Whether the MOU is renewed, replaced or allowed to lapse on 16 August.','Actual transit tonnage — no primary AIS data ingested.','Whether the attacks are state-directed or attributable to proxies.'],
 items:['i2'], questions:[], triggers:['t1']},

{id:'fed', name:'Fed policy & the September decision', dossiers:['econ'], types:['market'],
 status:'moved', opened:'22 May 2026', lastChange:'13 August 2026', events:96,
 summary:'Rate path under Chair Kevin Warsh, and the gap between market pricing and public framing.',
 state:[
  {k:'Implied Sep hike', v:'34%',        since:'13 Aug', flag:'hot'},
  {k:'Prior month',      v:'75%+ (13 Jul)', since:'13 Jul', flag:''},
  {k:'Direction of debate', v:'Hike or hold — not cut', since:'13 Jul', flag:'warn'},
  {k:'Long-end yields',  v:'Risen since 22 May', since:'22 May', flag:''},
  {k:'Headline inflation', v:'Cooling, 2nd consecutive month', since:'Aug', flag:'ok'},
  {k:'Chair',            v:'Kevin Warsh',  since:'22 May', flag:''}],
 history:[
  {d:'13 Aug', c:'Implied hike → 34%. Second consecutive cooling print.', s:'CNBC; market pricing'},
  {d:'13 Jul', c:'Implied hike → 75%+. Tightening becomes base case.', s:'Market pricing'},
  {d:'22 May', c:'Beat opened on chair transition. Warsh sworn in.', s:'—'}],
 unknown:['July CPI and PPI have not been read from the primary BLS release.','Whether long-end movement reflects term premium or inflation expectations.'],
 items:['i3'], questions:[], triggers:['t5']},

{id:'prices', name:'Fuel & grocery prices', dossiers:['econ','iran'], types:['market'],
 status:'moved', opened:'12 January 2026', lastChange:'14 August 2026', events:340,
 summary:'The prices households actually encounter, and their transmission from the Gulf.',
 state:[
  {k:'Brent',   v:'$86.91 (open, 14 Aug)', since:'14 Aug', flag:'warn'},
  {k:'AAA national average', v:'$4.06 (6 Aug)', since:'6 Aug', flag:'warn'},
  {k:'Two weeks prior', v:'$4.01 (28 Jul)', since:'28 Jul', flag:''},
  {k:'Direction', v:'Rising', since:'Aug', flag:'hot'}],
 history:[
  {d:'14 Aug', c:'Brent $86.91 at open, tracking Hormuz disruption.', s:'Market data'},
  {d:'6 Aug',  c:'AAA average → $4.06 from $4.01.', s:'AAA'}],
 unknown:['Grocery basket data not ingested. Utility rates not ingested.','How much of the fuel move is Hormuz versus refinery maintenance.'],
 items:['i2'], questions:[], triggers:[]},

{id:'agenda', name:'The regulatory agenda', dossiers:['power'], types:['reg'],
 status:'moved', opened:'14 August 2026', lastChange:'14 August 2026', events:4,
 summary:'The executive branch’s own published plan for every rule it intends to write, and the arithmetic behind its savings claims.',
 state:[
  {k:'Planned actions', v:'3,300+',        since:'14 Aug', flag:'hot'},
  {k:'Agency agendas',  v:'78',            since:'14 Aug', flag:''},
  {k:'Claimed net savings, FY26', v:'~$1.1tn', since:'14 Aug', flag:'warn'},
  {k:'Projected by 30 Sep', v:'$1.5tn',    since:'14 Aug', flag:'warn'},
  {k:'Concentration',   v:'Largely one unnamed rulemaking', since:'14 Aug', flag:'hot'},
  {k:'National coverage', v:'None identified', since:'14 Aug', flag:'hot'}],
 history:[
  {d:'14 Aug', c:'Beat opened on publication of the 2026 Unified Agenda.', s:'Federal Register'}],
 unknown:['Which rulemaking accounts for most of the $1.1tn.','The primary text has not been retrieved — only secondary analyses.','How the savings are computed, and against what baseline.'],
 items:['i1'], questions:['q1'], triggers:['t6']},

{id:'compliance', name:'DOJ compliance with the Transparency Act', dossiers:['records','power'], types:['oversight','case'],
 status:'moved', opened:'June 2026', lastChange:'13 August 2026', events:61,
 summary:'Whether the Justice Department is complying with court orders on release of the Epstein records, and what the pattern of withholding indicates.',
 state:[
  {k:'Compliance',      v:'Found incomplete',      since:'Jun',    flag:'hot'},
  {k:'Contempt',        v:'Noticed as available',  since:'13 Aug', flag:'hot'},
  {k:'Handwritten notes', v:'Withheld — asserted “duplicative”', since:'13 Aug', flag:'hot'},
  {k:'Redaction justifications', v:'Not produced', since:'13 Aug', flag:'hot'},
  {k:'Presiding judge', v:'Emmet Sullivan',        since:'Jun',    flag:''},
  {k:'Government counsel', v:'Todd Blanche, AG',   since:'—',      flag:''}],
 history:[
  {d:'13 Aug', c:'Contempt → noticed as available. Court presses on redaction documentation and withheld notes.', s:'Open court; NBC, Courthouse News'},
  {d:'Jun',    c:'Order → produce handwritten notes underlying FD-302 reports, or justify withholding.', s:'Court order'},
  {d:'25 Jun', c:'Standing established — informational injury recognised.', s:'Court ruling'}],
 unknown:['Why notes were released for some interview reports and not others.','How many documents remain unproduced. No production index has been obtained.','Whether contempt proceedings will actually be initiated.'],
 items:['o2'], questions:['q2'], triggers:[]},

{id:'kennedy', name:'The Kennedy Center', dossiers:['power'], types:['inst','case'],
 status:'recirculating', opened:'February 2026', lastChange:'13 August 2026', events:44,
 summary:'Control, naming and closure of the national performing arts centre, and the statute that governs it.',
 state:[
  {k:'Renaming',   v:'Voted 20–3',              since:'13 Aug', flag:'warn'},
  {k:'Legal status', v:'Contested — court struck attempt 1', since:'May', flag:'hot'},
  {k:'Building',   v:'Closing for two years',   since:'13 Aug', flag:''},
  {k:'Dissent',    v:'3 ex-officio congressional seats only', since:'13 Aug', flag:''}],
 history:[
  {d:'13 Aug', c:'Renaming → voted 20–3. Building → closing two years.', s:'Board vote; CBS, CNN'},
  {d:'May',    c:'Legal status → struck. Dual renaming held to violate the founding statute.', s:'Judge Christopher Cooper'}],
 unknown:['Whether a new challenge has been filed.','Whether the renaming takes effect before or after any ruling.'],
 items:['o1'], questions:[], triggers:[]},

{id:'mangione', name:'United States v. Mangione', dossiers:['violence','econ'], types:['case'],
 status:'moved', opened:'December 2025', lastChange:'14 August 2026', events:187,
 summary:'The federal and state prosecutions arising from the killing of the UnitedHealthcare chief executive.',
 state:[
  {k:'Federal charges', v:'Resolved by plea — 2 counts stalking resulting in death', since:'14 Aug', flag:'hot'},
  {k:'Capital exposure', v:'None — murder count struck', since:'14 Aug', flag:'ok'},
  {k:'Federal sentencing', v:'18 December',    since:'14 Aug', flag:''},
  {k:'State prosecution', v:'Pending — 8 September', since:'—',  flag:'warn'},
  {k:'Double jeopardy', v:'Unresolved',        since:'14 Aug', flag:'hot'}],
 history:[
  {d:'14 Aug', c:'Federal charges → resolved by plea. Capital exposure → none. Allocution entered: “I shot Mr. Thompson and he died.” New fact: posed as investor to confirm conference location.', s:'Federal court; NBC, CNN'},
  {d:'—',      c:'Murder count struck by the court, removing capital exposure.', s:'Court'},
  {d:'Dec 25', c:'Beat opened on arrest and charging.', s:'—'}],
 unknown:['Whether the federal plea affects the state prosecution.','What the plea agreement contains beyond the counts.'],
 items:['i5'], questions:['q3'], triggers:['t4','t8'], closesAfter:'18 December 2026'},

{id:'robinson', name:'State v. Robinson', dossiers:['violence'], types:['case'],
 status:'recirculating', opened:'September 2025', lastChange:'11 August 2026', events:203,
 summary:'The prosecution arising from the killing of Charlie Kirk, and the fight over capital eligibility.',
 state:[
  {k:'Stage',        v:'Pre-trial — probable cause pending', since:'Jul', flag:''},
  {k:'Capital exposure', v:'Contested — motion to strike aggravator', since:'11 Aug', flag:'warn'},
  {k:'Defence argument', v:'Single shot hit intended target; no risk to others', since:'11 Aug', flag:''},
  {k:'Next decision', v:'1 September — Judge Tony Graf Jr.', since:'Jul', flag:'warn'}],
 history:[
  {d:'11 Aug', c:'Capital exposure → contested. 41-page brief filed to strike the sole aggravating factor.', s:'Court filing; The Hill'},
  {d:'Jul',    c:'Preliminary hearing concludes; briefing ordered ahead of a 1 September ruling.', s:'Court'}],
 unknown:['How the court reads the aggravator statute on risk to bystanders.'],
 items:['o4'], questions:[], triggers:['t3']},

{id:'wells', name:'The death of Nolan Wells', dossiers:['account'], types:['death','oversight'],
 status:'moved', opened:'6 July 2026', lastChange:'14 August 2026', events:78,
 summary:'The unexplained death of an 18-year-old found off Horn Island, and the question of federal jurisdiction.',
 state:[
  {k:'Cause of death',  v:'Not publicly determined', since:'6 Jul',  flag:'hot'},
  {k:'Manner of death', v:'Not publicly determined', since:'6 Jul',  flag:'hot'},
  {k:'Federal review',  v:'Requested — response due 20 Aug', since:'13 Aug', flag:'warn'},
  {k:'Jurisdiction',    v:'Unresolved — Horn Island federal status', since:'—', flag:'hot'},
  {k:'Grand jury',      v:'Possible within 30 days', since:'13 Aug', flag:''},
  {k:'Addressed to',    v:'AG Todd Blanche; FBI Dir. Kash Patel', since:'13 Aug', flag:''}],
 history:[
  {d:'14 Aug', c:'Federal review → receipt confirmed by the Department.', s:'DOJ statement'},
  {d:'13 Aug', c:'Federal review → requested. Seven-day response clock starts.', s:'Congressional Black Caucus letter'},
  {d:'6 Jul',  c:'Beat opened. Body recovered off Horn Island.', s:'—'},
  {d:'4 Jul',  c:'Failed to return from a boating trip.', s:'—'}],
 unknown:['Cause and manner of death.','Whether Horn Island’s status makes a federal review available.','Whether the seven-day deadline will be met.'],
 items:['i4'], questions:['q4'], triggers:['t2']},

{id:'flock', name:'Flock & plate-reader networks', dossiers:['surv'], types:['tech'],
 status:'recirculating', opened:'March 2026', lastChange:'13 August 2026', events:156,
 summary:'A nationwide automated licence-plate network, documented misuse of it, and the local politics of withdrawal.',
 state:[
  {k:'Default retention', v:'7 days (was 30)', since:'13 Aug', flag:'ok'},
  {k:'Camera locations',  v:'120,000+ across 49 states', since:'13 Aug', flag:''},
  {k:'Jurisdictions withdrawn', v:'50+ since January', since:'13 Aug', flag:'warn'},
  {k:'Cross-agency search', v:'Restrictable by offence type', since:'13 Aug', flag:'ok'},
  {k:'Documented misuse',  v:'4 arrests, Richmond County SO', since:'Jun', flag:'hot'}],
 history:[
  {d:'13 Aug', c:'Retention → 7 days. Cross-agency search → restrictable by offence type. Emergency overrides → auto-flagged.', s:'Company announcement via AP'},
  {d:'Jun',    c:'Documented misuse → 4 employees arrested and fired for personal searches.', s:'Richmond County'}],
 unknown:['Whether retention applies retroactively to stored data.','Whether federal access is affected by per-offence restrictions.','Who audits the audit logs.'],
 items:['o3'], questions:[], triggers:[]},

{id:'dcpolice', name:'Federal policing in the District', dossiers:['account','immig'], types:['oversight'],
 status:'unresolved', opened:'August 2025', lastChange:'—', events:412,
 summary:'Federal control of District policing, National Guard deployment, and cooperation with immigration enforcement.',
 state:[
  {k:'Guard deployment', v:'Extended through January 2029', since:'—', flag:'warn'},
  {k:'MPD immigration cooperation', v:'Order date unresolved — see hold', since:'—', flag:'hot'},
  {k:'Arrests on federal warrants alone', v:'Barred', since:'Aug 2025', flag:''}],
 history:[
  {d:'14 Aug', c:'Item held. A circulating order could not be dated; publication blocked.', s:'Internal hold'}],
 unknown:['Whether a new MPD order exists or the 2025 order is recirculating.','Current arrest and referral counts. Not ingested.'],
 items:['o5'], questions:[], triggers:[]},

{id:'detention', name:'ICE detention conditions', dossiers:['immig','account'], types:['oversight','death'],
 status:'quiet', opened:'February 2026', lastChange:'12 August 2026', events:189,
 summary:'Conditions, deaths and procurement across immigration detention.',
 state:[
  {k:'Deaths reported in custody, 2026', v:'Not compiled — no primary source ingested', since:'—', flag:'warn'},
  {k:'Post-release death reporting', v:'Limited by policy', since:'—', flag:'hot'},
  {k:'Procurement',    v:'Electric-shock gloves solicited', since:'12 Aug', flag:'warn'}],
 history:[{d:'12 Aug', c:'Procurement → solicitation for electric-shock gloves reported.', s:'Reuters'}],
 unknown:['Total in-custody deaths this year.','Whether the solicitation proceeded to award.'],
 items:[], questions:[], triggers:[]},

{id:'vaccines', name:'The childhood vaccine schedule', dossiers:['health','power'], types:['reg'],
 status:'quiet', opened:'10 August 2026', lastChange:'10 August 2026', events:52,
 summary:'An executive order narrowing the universal schedule, and whether it can be executed.',
 state:[
  {k:'Universally recommended shots', v:'11 (from 17)', since:'10 Aug', flag:'warn'},
  {k:'MMR',        v:'To be split into three, “once available domestically”', since:'10 Aug', flag:'hot'},
  {k:'Domestic supply of components', v:'Does not exist', since:'10 Aug', flag:'hot'},
  {k:'HHS task force plan', v:'Due ~8 November', since:'10 Aug', flag:''}],
 history:[{d:'10 Aug', c:'Beat opened. Order signed; schedule narrowed; MMR split directed.', s:'Executive order'}],
 unknown:['Whether any manufacturer intends to produce standalone components.','What “once available” means as a legal condition.'],
 items:[], questions:['q5'], triggers:['t7']},

{id:'redistricting', name:'Mid-decade redistricting', dossiers:['elect'], types:['case'],
 status:'quiet', opened:'2025', lastChange:'—', events:267,
 summary:'Maps redrawn between censuses, and the litigation over them.',
 state:[
  {k:'Texas',      v:'2025 map blocked; 2021 lines in use', since:'Nov 2025', flag:''},
  {k:'California', v:'New map cleared for use',  since:'—', flag:''},
  {k:'Virginia',   v:'Plan struck down 4–3',     since:'—', flag:''}],
 history:[{d:'—', c:'No change this cycle.', s:'—'}],
 unknown:['Appeals pending in more than one state. Docket not ingested.'],
 items:[], questions:[], triggers:[]},

{id:'datacentres', name:'Data centres & the grid', dossiers:['energy'], types:['tech'],
 status:'quiet', opened:'April 2026', lastChange:'—', events:143,
 summary:'Load growth from computing, who pays for it, and where local government is refusing.',
 state:[
  {k:'Federal posture', v:'Pro-buildout; voluntary ratepayer pledge', since:'Jul', flag:''},
  {k:'Local restrictions', v:'Moratoria and refusals in multiple states', since:'—', flag:'warn'}],
 history:[{d:'—', c:'No change this cycle.', s:'—'}],
 unknown:['Ratepayer impact figures. Not ingested.'],
 items:[], questions:[], triggers:[]},

{id:'derecho', name:'The August Midwest derecho', dossiers:['disaster'], types:['event'],
 status:'receding', opened:'11 August 2026', lastChange:'12 August 2026', events:88,
 summary:'A confirmed derecho across the Ohio Valley, its casualties and the restoration.',
 state:[
  {k:'Deaths',   v:'3',                 since:'12 Aug', flag:'hot'},
  {k:'Peak outages', v:'~800,000 customers', since:'12 Aug', flag:'warn'},
  {k:'Tornadoes', v:'6+ confirmed or preliminary', since:'12 Aug', flag:''},
  {k:'Restoration', v:'Ongoing — current figure not ingested', since:'—', flag:'warn'}],
 history:[
  {d:'12 Aug', c:'Deaths → 3. Outages → ~800,000 across IL, IN, OH, KY.', s:'NBC, weather.com'},
  {d:'11 Aug', c:'Beat opened. Derecho, 100mph winds, flooding.', s:'NWS'}],
 unknown:['Current outage count.','Federal disaster declaration status.'],
 items:[], questions:[], triggers:[], closesAfter:'restoration complete'}
],

/* ---------- ITEMS ---------- */
items:[
{id:'i1',kind:'lead',stamp:'derived',beats:['agenda'],
 eyebrow:['Primary document','Federal Register','14 August'],
 title:'The government published its plan for 3,300 new rules. Three organisations read it.',
 deck:'The 2026 Unified Agenda is the executive branch’s own map of every regulation it intends to write before 2029. It came out this morning. No national outlet has covered it.',
 body:[
  'The document runs to <strong>78 separate agency agendas</strong> and lists <strong>more than 3,300 planned rulemaking actions</strong> — the largest such total in a decade. It is the closest thing that exists to a schedule of what the federal government will do to regulated industry over the next three years, and it is published in full, for free, twice a year.',
  'It also carries the administration’s own scorekeeping. Agencies have booked roughly <strong>$1.1 trillion</strong> in claimed net regulatory savings so far in fiscal 2026, and the Agenda projects that figure will reach <strong>$1.5 trillion by 30 September</strong>.',
  'That number has a hole in it. Analysts who have read the Agenda note the $1.1 trillion is <strong>largely attributable to a single rulemaking</strong> — and do not say which one. A trillion-dollar claim resting on one rule is a different claim than one resting on 3,300. Identifying that rule is the first thing worth doing with this document, and the data to do it is public and sitting unexamined.'],
 timeline:[{l:'Published',d:'14 Aug',s:'now'},{l:'Rules proposed',s:'pending'},{l:'Finalised',s:'pending'},{l:'Effective',s:'pending'}],
 derived:'Flagged by consequence-to-coverage ratio: a primary document of term-length scope with three identifiable readers and no national pickup. Volume ranking scored it zero.',
 sources:[
  {n:'2026 Regulatory Plan and Unified Agenda',u:'https://www.federalregister.gov/documents/2026/08/14/2026-16626/2026-regulatory-plan-and-unified-agenda-of-federal-regulatory-and-deregulatory-actions',t:'documentation',c:'—'},
  {n:'American Action Forum analysis',u:'https://www.americanactionforum.org/insight/the-2026-unified-agenda-checking-in-on-the-trump-2-0-deregulatory-agenda/',t:'techreport',c:'0.75'},
  {n:'GWU Regulatory Studies Center',u:'https://regulatorystudies.columbian.gwu.edu/trumps-2026-unified-agenda',t:'techreport',c:'0.75'}],
 note:'Primary text not retrieved — federalregister.gov returned an access interstitial. All figures are second-hand and confidence is capped accordingly.',
 questions:['q1']},

{id:'i2',kind:'wire',stamp:'derived',beats:['hormuz','prices'],
 title:'A 60-day guarantee on Gulf shipping expires Saturday. It stopped working in early August.',
 deck:'The only document either side has signed on freedom of navigation since the April ceasefire runs out this weekend, on an arrangement already abandoned.',
 body:[
  'The memorandum signed by Trump and Pezeshkian on 17 June declared the removal of the American naval blockade and arranged safe passage for commercial vessels at no charge — <strong>“for 60 days only.”</strong> Sixty days from 17 June falls on <strong>Saturday, 16 August</strong>.',
  'The guarantee did not survive its own term. The United States reimposed the blockade in early August after renewed attacks on commercial shipping and on several Arab states. Yesterday two more vessels were struck in the Strait, transit slowed to a near standstill, and Defence Secretary Pete Hegseth said the Navy can hold the blockade indefinitely.',
  'Brent opened near <strong>$86.91</strong>. The AAA national average was <strong>$4.06</strong> on 6 August against $4.01 on 28 July — the transmission line from this beat into household costs, and from household costs into November.'],
 timeline:[{l:'Ceasefire',d:'7 Apr',s:'done'},{l:'MOU lifts blockade',d:'17 Jun',s:'done'},{l:'Reimposed',d:'early Aug',s:'done'},{l:'Hardened',d:'14 Aug',s:'now'},{l:'Term ends',d:'16 Aug',s:'pending'}],
 derived:'Date arithmetic on a stored term length. The MOU’s “60 days only” was recorded on 17 June; no source reports the expiry date, and the beat state computed it.',
 sources:[
  {n:'Times of Israel — liveblog 14 Aug',u:'https://www.timesofisrael.com/liveblog-august-14-2026/',t:'news',c:'0.6'},
  {n:'CNN — Hormuz traffic, 13 Aug',u:'https://edition.cnn.com/2026/08/13/world/live-news/iran-war-trump',t:'news',c:'0.6'},
  {n:'CRS — Strait of Hormuz security',u:'https://www.congress.gov/crs-product/R45281',t:'techreport',c:'0.8'}],
 questions:[]},

{id:'i3',kind:'wire',stamp:'derived',beats:['fed'],
 title:'The September question is a rate hike, not a cut',
 deck:'A tightening scenario that was the base case in mid-July has been more than halved. Coverage still framed around a cut is working from a position that expired weeks ago.',
 body:[
  'Market-implied odds of a quarter-point <strong>increase</strong> at the September meeting stood at <strong>34 per cent</strong> on 13 August, down from above <strong>75 per cent</strong> a month earlier, after a second consecutive month of cooling headline inflation.',
  'The direction matters more than the number. Yields at the long end have risen since Chair Kevin Warsh was sworn in on 22 May, which is the opposite of what an easing path would produce.'],
 timeline:[{l:'Warsh sworn in',d:'22 May',s:'done'},{l:'Hike odds 75%',d:'13 Jul',s:'done'},{l:'Hike odds 34%',d:'13 Aug',s:'now'},{l:'FOMC',d:'Sep',s:'pending'}],
 derived:'Frame correction. Detected by comparing the stored beat position from 13 July against today’s, rather than by reading either day in isolation.',
 sources:[
  {n:'CNBC — hike odds tumble',u:'https://www.cnbc.com/2026/08/07/odds-the-fed-hikes-in-september-tumble-following-big-july-jobs-miss.html',t:'news',c:'0.6'},
  {n:'Motley Fool — 14 Aug',u:'https://www.fool.com/investing/2026/08/14/lower-odds-fed-rate-hike-sinister-inflation-metric/',t:'news',c:'0.5'}],
 note:'July CPI and PPI were not retrieved from the primary BLS release and are not asserted here.',
 questions:[]},

{id:'i4',kind:'wire',stamp:'open',beats:['wells'],
 title:'Seven days to answer on Nolan Wells',
 deck:'A federal response clock is running, and the question underneath it — whether Horn Island is federal land — is not being asked plainly.',
 body:[
  'The Congressional Black Caucus has asked Attorney General Todd Blanche and FBI Director Kash Patel for an independent federal review of the death of 18-year-old Nolan Wells, whose body was found off Horn Island on 6 July after he failed to return from a 4 July boating trip. The letter gives federal officials <strong>seven days</strong> to respond. That deadline is <strong>20 August</strong>. The Department confirms receipt.',
  'The pivot is jurisdictional. If Horn Island’s federal status is what makes a federal review available, the answer determines whether this becomes a federal matter or stays a Mississippi one. The family’s attorney says a grand jury review could come within thirty days.',
  '<strong>Non-response is a recordable event.</strong> If 20 August passes without an answer, that is logged here as a finding, not as an absence.'],
 timeline:[{l:'Body found',d:'6 Jul',s:'done'},{l:'Letter sent',d:'13 Aug',s:'done'},{l:'Receipt confirmed',d:'14 Aug',s:'now'},{l:'Response due',d:'20 Aug',s:'pending'},{l:'Grand jury',d:'~30d',s:'pending'}],
 sources:[
  {n:'Congressional Black Caucus letter',u:'https://cbc.house.gov/news/documentsingle.aspx?DocumentID=3228',t:'documentation',c:'0.85'},
  {n:'Newsweek — Horn Island federal status',u:'https://www.newsweek.com/nolan-wells-doj-review-horn-island-federal-status-12319939',t:'news',c:'0.55'},
  {n:'ABC News',u:'https://abcnews.com/US/congressional-black-caucus-urges-doj-review-nolan-wells/story?id=135619833',t:'news',c:'0.6'}],
 questions:['q4']},

{id:'i5',kind:'wire',stamp:'documented',beats:['mangione'],
 title:'Mangione pleaded to stalking, not murder',
 deck:'The charge the plea actually resolves is narrower than the coverage implies, and the September state trial is untouched by it so far.',
 body:[
  'The plea entered in federal court this morning was to <strong>two counts of stalking resulting in death</strong>. The murder charge that carried the death penalty had already been struck by the court. “I shot Mr. Thompson and he died,” he told the judge, and said he had <strong>posed as a potential investor</strong> to confirm the location of the conference.',
  'Sentencing is set for 18 December. The New York state murder prosecution remains on the calendar for <strong>8 September</strong>, and whether this plea disturbs it is unresolved.'],
 timeline:[{l:'Charged',s:'done'},{l:'Murder count struck',s:'done'},{l:'Pled guilty',d:'14 Aug',s:'now'},{l:'State trial',d:'8 Sep',s:'pending'},{l:'Sentencing',d:'18 Dec',s:'pending'}],
 derived:'Scheduled trigger, resolved on the predicted date. The stored expectation was “expected to plead guilty”; the recorded outcome differs in charge, which is the delta.',
 sources:[
  {n:'NBC News',u:'https://www.nbcnews.com/news/us-news/luigi-mangione-guilty-plea-federal-court-case-ceo-shooting-rcna592421',t:'news',c:'0.6'},
  {n:'CNN live coverage',u:'https://www.cnn.com/2026/08/14/us/live-news/luigi-mangione-hearing-plea-deal-talks',t:'news',c:'0.6'},
  {n:'Forbes',u:'https://www.forbes.com/sites/alisondurkee/2026/08/14/luigi-mangione-expected-to-plead-guilty-in-federal-court-today/',t:'news',c:'0.55'}],
 questions:['q3']},

{id:'o1',kind:'omission',beats:['kennedy'],who:'Kennedy Center',
 title:'The 20–3 vote was the second attempt',
 short:'The 20–3 vote was the <b>second attempt</b>. Judge Christopher Cooper struck the first renaming in May as a violation of the statute that created the institution. The three votes against came from Beatty, Whitehouse and Larsen — <b>the ex-officio congressional members</b>, the only seats the board cannot appoint.',
 body:['After a roughly two-hour meeting on 13 August the board voted 20–3 to rename the building and plaza for the president and to close for two years of renovations.',
  'The state change is not the vote. It is that a court has already ruled against this once. In May, U.S. District Judge Christopher Cooper held that renaming the centre after both Kennedy and Trump violated the federal statute that created it. The board proceeded anyway, which leaves the action <strong>ordered but not legally effective</strong>.',
  'Reading the vote for structure rather than outcome: the only dissent came from the three seats the board cannot appoint.'],
 timeline:[{l:'Attempt 1',d:'May',s:'done'},{l:'Struck down',d:'May',s:'done'},{l:'Board vote 20–3',d:'13 Aug',s:'done'},{l:'Contested',s:'contested'},{l:'Legally effective',s:'pending'}],
 sources:[{n:'CBS News',u:'https://www.cbsnews.com/news/kennedy-center-board-votes-trump-name-joyce-beatty/',t:'news',c:'0.6'},
  {n:'CNN Politics',u:'https://www.cnn.com/2026/08/13/politics/kennedy-center-board-vote',t:'news',c:'0.6'}]},

{id:'o2',kind:'omission',beats:['compliance'],who:'Epstein files',
 title:'Two different kinds of statement, run together',
 short:'DOJ told Judge Sullivan the Attorney General deemed all FBI handwritten interview notes <b>“duplicative.”</b> A former prosecutor says the Department’s own production contradicts that. Those are two different kinds of statement, and today’s coverage merges them.',
 body:['Judge Emmet Sullivan put Justice Department attorneys on formal notice that contempt proceedings are available if the department keeps failing to comply, and reminded the room that contempt findings he made nearly two decades ago followed those lawyers into later judgeship bids. That is an escalation in remedy, not in tone.',
  '<strong>What the government said</strong> — an assistant U.S. attorney told the court the Attorney General had determined all the handwritten notes were “duplicative.” That is a documented fact about a representation made in open court.',
  '<strong>What is alleged about it</strong> — a former prosecutor states the production contradicts this, because handwritten notes were released alongside interview reports for some interviews and not others. That is a credible allegation from an identified source with direct knowledge, not independently verified.',
  'Held at separate tiers deliberately. The withheld notes concern interviews with a woman who says Epstein introduced her to Trump when she was around thirteen. The <strong>pattern</strong> of what is withheld is a finding independent of what the notes contain.'],
 timeline:[{l:'Production ordered',d:'Jun',s:'done'},{l:'Non-compliance found',s:'done'},{l:'Contempt noticed',d:'13 Aug',s:'now'},{l:'Proceedings',s:'pending'}],
 sources:[{n:'NBC News',u:'https://www.nbcnews.com/politics/justice-department/judge-shows-signs-frustration-doj-attorneys-handling-epstein-files-rcna592418',t:'news',c:'0.6'},
  {n:'Courthouse News',u:'https://www.courthousenews.com/feds-struggle-to-explain-redactions-in-epstein-files-compliance-case/',t:'news',c:'0.6'}],
 questions:['q2']},

{id:'o3',kind:'omission',beats:['flock'],who:'Flock',
 title:'Announced yesterday, carried today by eight outlets',
 short:'Announced <b>yesterday</b>. Carried today by eight outlets with no fact added since: retention cut from 30 days to seven, flagged emergency overrides, per-offence restrictions on outside searches, 120,000 camera locations, 50-plus jurisdictions cancelled.',
 body:['Every substantive fact in today’s coverage was already in yesterday’s record: retention cut from 30 days to seven, automatically flagged emergency overrides, per-offence-type restrictions letting a jurisdiction block immigration-related queries, more than 120,000 camera locations across 49 states, and over 50 jurisdictions cancelling or suspending since January per DeFlock’s tracker. Four Richmond County Sheriff’s Office employees have been arrested and fired since June over personal searches.',
  'The underlying development is real and consequential. It happened on 13 August. Today it was republished.'],
 derived:'Recirculation detected by comparing first-seen timestamps against publication dates across the cluster. Eight outlets, one first-seen date, zero new claims.',
 sources:[{n:'AP via Washington Post',u:'https://www.washingtonpost.com/business/2026/08/13/flock-license-plate-cameras-surveillance-deflock/bced9880-9725-11f1-9ef9-1be722184483_story.html',t:'news',c:'0.6'}]},

{id:'o4',kind:'omission',beats:['robinson'],who:'Tyler Robinson',
 title:'The brief covered today was filed Tuesday',
 short:'The 41-page brief on the death penalty was filed <b>Tuesday</b>. Nothing has changed in the case since. The next decision is Judge Tony Graf Jr. on probable cause, <b>1 September</b>.',
 body:['The 41-page defence brief — arguing the sole aggravating factor must be struck because a single shot that “hit the intended target” did not create the statutorily required risk to others — was filed and made public on Tuesday 11 August. Today’s coverage adds nothing to it.',
  'The next actual state change in this case is 1 September, when Judge Tony Graf Jr. is expected to rule on whether there is probable cause to send it to trial.'],
 derived:'Recirculation. Filing date 11 August; coverage cluster peaked 14 August with no new claims entered.',
 sources:[{n:'The Hill',u:'https://thehill.com/regulation/court-battles/6026466-kirk-tyler-robinson-death-penalty-defense/',t:'news',c:'0.6'}]},

{id:'o5',kind:'omission',stamp:'hold',beats:['dcpolice'],who:'D.C. police and ICE',
 title:'Not published — we could not establish whether a new order exists',
 short:'<b>Not published.</b> An information-sharing order attributed to Chief Pamela Smith is circulating as current, but the order it appears to describe dates to August 2025. We could not establish whether a new order exists and are not reporting it either way.',
 body:['Today’s immigration-enforcement cluster surfaces an item describing a D.C. police order permitting information sharing with federal immigration agencies at traffic stops while barring arrests on federal warrants alone.',
  'The order that description matches — issued by Chief Pamela Smith, permitting sharing on people not in custody and transport of federal agents and detainees, while barring database checks solely for immigration status — appears in sources dated <strong>August 2025</strong>.',
  'It is therefore either a genuinely new order or a year-old one recirculating during a period of renewed federal enforcement activity in the District. That could not be resolved, so nothing is asserted. The item is held rather than published.'],
 derived:'Held by the date-conflict check: cluster first-seen is today, but the earliest matching source predates it by roughly twelve months. Publication blocked pending resolution.',
 sources:[]}
],

questions:[
 {id:'q1',beat:'agenda',q:'Which single rulemaking accounts for most of the $1.1tn in claimed savings?',known:'Analysts note the total is largely attributable to one rule. The rule is unnamed in all available coverage.',who:'OIRA · Regulatory Information Service Center · agency RIN owners',doc:'reginfo.gov agency rule lists; the rule’s own regulatory impact analysis',next:'Immediate — the data is public and unread',opened:'14 Aug 2026',status:'Never investigated'},
 {id:'q2',beat:'compliance',q:'Why were handwritten notes released for some FBI interview reports and withheld for others?',known:'DOJ told the court the Attorney General deemed all notes duplicative. A former prosecutor says the production itself contradicts that.',who:'Todd Blanche · the assistant U.S. attorney of record · the FBI custodian',doc:'The production index; filings on Sullivan’s compliance docket',next:'Next DOJ filing',opened:'Carried forward',status:'Open · escalating'},
 {id:'q3',beat:'mangione',q:'Does the federal plea bar or complicate the New York prosecution?',known:'Federal plea entered 14 August to stalking resulting in death; state murder trial scheduled 8 September.',who:'Manhattan District Attorney · defence counsel · the state trial court',doc:'Any pre-trial motion filed before 8 September',next:'Daily until 8 Sep',opened:'14 Aug 2026',status:'Open'},
 {id:'q4',beat:'wells',q:'Is Horn Island federal land for jurisdictional purposes?',known:'Federal status is raised in coverage as the pivot for whether a federal review is available. Not established.',who:'DOJ · National Park Service · Jackson County officials',doc:'DOJ’s response to the Congressional Black Caucus letter',next:'20 August — the seven-day deadline',opened:'Carried forward',status:'Open · deadline-bound'},
 {id:'q5',beat:'vaccines',q:'Do split MMR components have a supply path, or is the order unexecutable as written?',known:'The 10 August order cuts universally recommended shots from 17 to 11 and directs MMR be split “once available domestically.” Standalone components are not currently manufactured in the United States.',who:'HHS task force · Merck · FDA CBER',doc:'The 90-day HHS task force plan',next:'~8 November',opened:'Carried forward',status:'Open · “once available” is doing the work'}
],

triggers:[
 {id:'t1',d:'16 AUG',sort:'2026-08-16',t:'Iran MOU expires',s:'60-day safe-passage term ends',beat:'hormuz',item:'i2'},
 {id:'t2',d:'20 AUG',sort:'2026-08-20',t:'DOJ / FBI deadline',s:'Wells review — silence is recordable',beat:'wells',item:'i4'},
 {id:'t3',d:'1 SEP', sort:'2026-09-01',t:'Robinson ruling',s:'Probable cause — Judge Graf',beat:'robinson',item:'o4'},
 {id:'t4',d:'8 SEP', sort:'2026-09-08',t:'Mangione state trial',s:'New York',beat:'mangione',item:'i5'},
 {id:'t5',d:'SEP',   sort:'2026-09-16',t:'FOMC decision',s:'Hike at 34 per cent implied',beat:'fed',item:'i3'},
 {id:'t6',d:'30 SEP',sort:'2026-09-30',t:'Fiscal year ends',s:'$1.5tn projection becomes checkable',beat:'agenda',item:'i1'},
 {id:'t7',d:'~8 NOV',sort:'2026-11-08',t:'HHS vaccine plan due',s:'90 days from the order',beat:'vaccines',item:null},
 {id:'t8',d:'18 DEC',sort:'2026-12-18',t:'Mangione sentencing',s:'Federal',beat:'mangione',item:'i5'}
],

contradictions:[
 {id:'c1',a:'“Removal of the naval blockade”',asrc:'MOU, 17 June',b:'“We can maintain it indefinitely”',bsrc:'Hegseth, 14 August',tier:'Documented fact',st:'Unreconciled. Term expires 16 August.',c:'0.75',beat:'hormuz',item:'i2',opened:'14 Aug'},
 {id:'c2',a:'Notes are “duplicative”',asrc:'DOJ, in open court',b:'Notes released for some reports, not others',bsrc:'Former prosecutor',tier:'Fact against allegation',st:'Disputed. Testable against the production index.',c:'0.45',beat:'compliance',item:'o2',opened:'13 Aug'},
 {id:'c3',a:'Dual renaming violates the statute',asrc:'Judge Cooper, May',b:'Board renames anyway, 20–3',bsrc:'Board, 13 August',tier:'Documented fact',st:'Direct conflict. Litigation expected.',c:'0.70',beat:'kennedy',item:'o1',opened:'13 Aug'}
],

archive:[
 {d:'14 August 2026', n:'001', items:10, note:'Current edition'}
]
};
