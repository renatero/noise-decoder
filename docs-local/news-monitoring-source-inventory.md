# News monitoring source inventory

**Purpose:** a practical seed list of public news, claims, and verification
sources for detecting possible information manipulation. This is a monitoring
inventory, **not** a list of outlets that have been judged propagandistic.
Publishing a story, holding an editorial viewpoint, or being state funded is
not evidence that a particular article is false or coordinated.

**Scope date:** 2026-11-14. This is a maintained starting inventory, not an
exhaustive catalogue of every publication in the listed regions.

## Rules for using this inventory

- Treat every item as a *source to compare*, never as an automatic truth or
  propaganda label.
- Preserve the original URL, headline/body text, visible publication time,
  author/byline where displayed, source domain, and collection time.
- Check a claim against independent reporting and primary material before
  showing a finding. Do not infer author intent, state control, bot identity,
  or deception from language, source, or political position alone.
- Ingest only public material in a way permitted by each site's terms, robots
  policy, rate limits, and applicable law. Prefer an official RSS/API feed;
  otherwise retain only a user-reviewed visible-page extract.
- Keep `actor_id` nullable. Many publisher listing pages do not reveal a
  meaningful author; never substitute the whole outlet or `unknown` as though
  it were one person.
- **SS.LV is not a news source.** It is a Latvian classified-advertising site.
  Keep it in a separate ads/listings collection and do not mix its listings
  with article-based news claims without an explicit research question.

## Suggested source record

Use this structure for each configured source:

```json
{
  "source_id": "fi-yle-news",
  "region": "finland",
  "name": "Yle News",
  "base_url": "https://yle.fi/news",
  "kind": "public-service-news",
  "languages": ["en", "fi", "sv"],
  "collection": "rss_or_user_visible_page",
  "monitoring_role": "comparison_baseline",
  "notes": "Store article URL and displayed publication time."
}
```

`kind` and `monitoring_role` are operational metadata, not reliability or
truth scores. Recommended roles are `comparison_baseline`,
`broad-news-discovery`, `claims-monitoring`, `fact-check`, and
`official-primary-source`.

## Finland

Finland has a diverse but concentrated media environment; the country's
[Reuters Institute profile](https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026/finland)
and [InfoFinland media overview](https://infofinland.fi/en/information-about-finland/media-in-finland)
are useful context for maintaining this list.

| Priority | Source / entry page | Languages | Role | Collection note |
| --- | --- | --- | --- | --- |
| 1 | [Yle News](https://yle.fi/news) / [RSS](https://yle.fi/rss/news) | EN, FI, SV and others | comparison baseline | Official RSS is preferred. |
| 1 | [Helsingin Sanomat](https://www.hs.fi/) | FI, some EN | broad news discovery | Respect paywalls; capture visible headline and link only if necessary. |
| 1 | [Ilta-Sanomat](https://www.is.fi/) | FI | broad news discovery | High-reach commercial news. |
| 1 | [Iltalehti](https://www.iltalehti.fi/) | FI | broad news discovery | High-reach commercial news. |
| 1 | [MTV Uutiset](https://www.mtvuutiset.fi/) | FI | broad news discovery | Broadcast and online news comparison. |
| 2 | [STT](https://sttinfo.fi/) | FI, SV, EN | wire / primary release tracking | Use public releases; much wire copy is licensed. |
| 2 | [Hufvudstadsbladet](https://www.hbl.fi/) | SV | Swedish-language coverage | Include language in all comparisons. |
| 2 | [Aamulehti](https://www.aamulehti.fi/) | FI | regional news | Tampere / Pirkanmaa perspective. |
| 2 | [Turun Sanomat](https://www.ts.fi/) | FI | regional news | Southwest Finland perspective. |
| 2 | [Kaleva](https://www.kaleva.fi/) | FI | regional news | Northern Finland perspective. |
| 2 | [Verkkouutiset](https://www.verkkouutiset.fi/) | FI | claims monitoring | Tag as political/news commentary; compare claims, not ideology. |
| 1 | [Faktabaari](https://faktabaari.fi/) | FI, EN | fact-check / context | Use verdicts as leads and read underlying evidence. |
| 1 | [Finnish Government](https://valtioneuvosto.fi/en/) | FI, SV, EN | official primary source | For Finnish government claims and releases. |

## Latvia

Latvia's information environment is multilingual, so Latvian, Russian, and
English coverage should be compared rather than collapsed. The
[Latvian ownership monitor](https://media-ownership.eu/2025-edition/country-reports/latvia/)
and [2023 national media-environment study](https://ppdb.mk.gov.lv/wp-content/uploads/2023/09/SIA-TNS-Latvia_Latvijas-Nacionalo-mediju-vide-petijums_Analitisks-zinojums_KM_2023-1.pdf)
identify LSM, Delfi, and TVNET among important online services.

| Priority | Source / entry page | Languages | Role | Collection note |
| --- | --- | --- | --- | --- |
| 1 | [LSM](https://www.lsm.lv/) / [English LSM](https://eng.lsm.lv/) / [RSS](https://eng.lsm.lv/feeds/rss/) | LV, EN, RU | comparison baseline | Public-service reporting; use language-specific URL as metadata. |
| 1 | [Delfi Latvia](https://www.delfi.lv/) | LV, RU | broad news discovery | Include Latvian and Russian editions where public. |
| 1 | [TVNET](https://www.tvnet.lv/) | LV, RU | broad news discovery | Store edition/language. |
| 2 | [Jauns.lv](https://jauns.lv/) | LV | broad news discovery | Mainstream online/news-magazine coverage. |
| 2 | [Apollo.lv](https://www.apollo.lv/) | LV | broad news discovery | Mainstream online coverage. |
| 2 | [TV3 Ziņas](https://zinas.tv3.lv/) | LV | broadcast-news comparison | Capture article URLs, not video transcripts without review. |
| 2 | [Latvijas Avīze](https://www.la.lv/) | LV | claims monitoring | Newspaper/editorial ecosystem. |
| 2 | [Ir](https://ir.lv/) | LV | analysis / investigation | Respect subscription limits. |
| 2 | [nra.lv](https://nra.lv/) | LV | claims monitoring | Compare high-impact claims with independent reporting. |
| 1 | [Re:Baltica](https://en.rebaltica.lv/) / [Re:Check](https://en.rebaltica.lv/category/fact-checking/) | LV, EN, RU | fact-check / investigation | Independent investigative and fact-checking context. |
| 1 | [Latvian Cabinet of Ministers](https://www.mk.gov.lv/en) | LV, EN | official primary source | Government statements and releases. |
| 1 | [Latvian State Police](https://www.vp.gov.lv/en) | LV, EN | official primary source | Use for claimed policing/security events. |

## Europe: cross-border and regional sources

Use cross-border outlets to compare national framing, and use fact-checking /
information-integrity services as evidence leads. The
[European Digital Media Observatory (EDMO)](https://digital-strategy.ec.europa.eu/en/policies/european-digital-media-observatory)
coordinates a network of independent fact-checkers and researchers across the
EU; it is a strong starting point for country-specific verification partners.

| Priority | Source / entry page | Languages | Role | Collection note |
| --- | --- | --- | --- | --- |
| 1 | [Reuters World / Europe](https://www.reuters.com/world/europe/) | EN, multilingual services | comparison baseline | Compare original Reuters URLs, not syndicated rewrites. |
| 1 | [Associated Press World News](https://apnews.com/world-news) | EN | comparison baseline | Especially useful for cross-border corroboration. |
| 1 | [AFP Fact Check](https://factcheck.afp.com/) | multilingual | fact-check | Verification lead; retain cited primary evidence. |
| 1 | [BBC News Europe](https://www.bbc.com/news/world/europe) | EN, multilingual services | broad news discovery | UK source covering European affairs. |
| 1 | [Deutsche Welle](https://www.dw.com/en/top-stories/s-9097) | DE, EN and many | broad news discovery | Useful language coverage and regional reporting. |
| 1 | [France 24](https://www.france24.com/en/europe/) | EN, FR and others | broad news discovery | Compare across languages. |
| 1 | [Euronews](https://www.euronews.com/) | multilingual | broad news discovery | Cross-European framing. |
| 1 | [POLITICO Europe](https://www.politico.eu/) | EN | EU policy / claims monitoring | Political reporting and analysis. |
| 2 | [EUobserver](https://euobserver.com/) | EN | EU policy / claims monitoring | Independent EU-affairs coverage. |
| 2 | [The Guardian Europe](https://www.theguardian.com/world/europe-news) | EN | broad news discovery | UK editorial framing comparison. |
| 2 | [Le Monde International](https://www.lemonde.fr/en/international/) | EN, FR | broad news discovery | French framing comparison. |
| 2 | [Der Spiegel International](https://www.spiegel.de/international/) | EN, DE | broad news discovery | German framing comparison. |
| 2 | [RFE/RL](https://www.rferl.org/) | multilingual | regional / claims monitoring | Especially relevant to Eastern Europe and Russia-related narratives. |
| 2 | [Bellingcat](https://www.bellingcat.com/) | EN | open-source investigation | Treat as a methodology-rich investigative source, not a sole verifier. |
| 1 | [EUvsDisinfo](https://euvsdisinfo.eu/) | multilingual | information-manipulation case database | Use documented cases as leads; do not auto-label matching language. |
| 1 | [European Commission information integrity](https://commission.europa.eu/topics/countering-information-manipulation_en) | EU languages | official primary / policy context | Definitions, policy, and partner links. |

### State-affiliated and restricted-source handling

Do not make direct collection from restricted sources the default. The EU
Council has documented restrictions on RT and Sputnik broadcasting directed at
the EU in relation to systematic information manipulation and disinformation:
[Council decision notice](https://www.consilium.europa.eu/en/press/press-releases/2022/03/02/eu-imposes-sanctions-on-state-owned-outlets-rtrussia-today-and-sputnik-s-broadcasting-in-the-eu/).

For analysis, record a source's declared ownership/affiliation when supported
by documentation, use lawful archived or third-party documented examples where
needed, and preserve the exact evidence. Never use the label “state-affiliated”
as proof that an individual claim is false.

## United States

For the U.S., cover broad-reach reporting plus a politically diverse claims
ecosystem. Editorial and opinion publishers belong in a monitored comparison
set; they are not automatically misinformation sources. During elections or
fast-moving incidents, prioritize primary public records and multiple
independent confirmations.

| Priority | Source / entry page | Role | Collection note |
| --- | --- | --- | --- |
| 1 | [Associated Press](https://apnews.com/) / [AP Fact Check](https://apnews.com/hub/ap-fact-check) | comparison baseline / fact-check | Strong wire baseline; use original links. |
| 1 | [Reuters U.S.](https://www.reuters.com/world/us/) / [Reuters Fact Check](https://www.reuters.com/fact-check/) | comparison baseline / fact-check | Separate news and fact-check URLs in metadata. |
| 1 | [NPR](https://www.npr.org/) | public-service news comparison | Include local-member coverage only when relevant. |
| 1 | [PBS NewsHour](https://www.pbs.org/newshour/) | public-service news comparison | Television and transcript comparison. |
| 1 | [ABC News](https://abcnews.go.com/), [CBS News](https://www.cbsnews.com/), [NBC News](https://www.nbcnews.com/) | broadcast-news comparison | Capture source and original air/article time. |
| 1 | [CNN](https://www.cnn.com/), [Fox News](https://www.foxnews.com/), [MSNBC](https://www.msnbc.com/) | high-reach claims monitoring | Separate reporting, commentary, clips, and hosts. |
| 1 | [The New York Times](https://www.nytimes.com/), [The Wall Street Journal](https://www.wsj.com/), [USA Today](https://www.usatoday.com/) | national newspaper comparison | Respect paywalls and licences. |
| 1 | [Politico](https://www.politico.com/), [Axios](https://www.axios.com/), [The Hill](https://thehill.com/) | politics / policy claims monitoring | Track original claim source when reporting on it. |
| 2 | [ProPublica](https://www.propublica.org/) | investigative reporting | Good for evidence-rich long-form reporting. |
| 2 | [Newsmax](https://www.newsmax.com/), [One America News](https://www.oann.com/) | high-reach claims monitoring | Do not apply automatic false/propaganda labels. |
| 2 | [Breitbart](https://www.breitbart.com/), [The Daily Wire](https://www.dailywire.com/), [The Daily Caller](https://dailycaller.com/) | high-reach claims monitoring | Opinion and reporting must be tagged separately. |
| 2 | [HuffPost](https://www.huffpost.com/), [Mother Jones](https://www.motherjones.com/) | high-reach claims monitoring | Opinion and reporting must be tagged separately. |
| 2 | [NewsNation](https://www.newsnationnow.com/) | broadcast / cable comparison | Include when a narrative has broad reach. |
| 1 | [FactCheck.org](https://www.factcheck.org/) | fact-check | A nonpartisan project of UPenn's Annenberg Public Policy Center; see its [mission](https://www.factcheck.org/about/our-mission/). |
| 1 | [PolitiFact](https://www.politifact.com/) | fact-check | Read methodology and funding disclosures alongside verdicts. |
| 1 | [Snopes](https://www.snopes.com/) | fact-check / viral claim monitoring | Useful for viral rumours; corroborate with primary sources. |
| 1 | [Congress.gov](https://www.congress.gov/), [White House](https://www.whitehouse.gov/), [Supreme Court](https://www.supremecourt.gov/) | official primary sources | Verify legal/policy claims against the underlying record. |

## Triage workflow

1. **Discover:** collect only a visible article/listing card, RSS item, or API
   record that has a source URL and capture time.
2. **Normalize:** retain the six extension fields. Add source metadata outside
   the event record: outlet, language, section, collection method, and
   publisher/author when actually displayed.
3. **Cluster cautiously:** use repeated URLs, near-duplicate claims, unusual
   timing, and cross-source propagation as leads—not proof of coordination.
4. **Verify:** compare at least two independent sources and the relevant
   primary record. Search EDMO/EUvsDisinfo and national fact-checkers for
   known claim variants.
5. **Report uncertainty:** use terms such as “unverified claim,” “contradicted
   by available evidence,” or “potential coordinated amplification.” Never
   call a person or outlet propagandistic solely from the detector output.
6. **Human review:** require a reviewer before publication, escalation, or any
   moderation action.

## First implementation set

Start with these feeds/pages before adding more adapters:

1. Yle News RSS, LSM English RSS, Reuters Europe, AP World, and Reuters U.S.
2. Finnish Faktabaari, Latvia's Re:Check, AFP Fact Check, FactCheck.org, and
   PolitiFact for verification context.
3. One source per language and market in the Finland/Latvia tables, then add
   outlets only when there is a clear monitoring question or demonstrated
   audience reach.

This keeps the initial dataset auditable and avoids an unreviewable scrape of
every news site.

## Social-network monitoring

News discussion often occurs away from the publisher's article page. Add a
publisher's verified/official account only after recording the account URL,
platform account ID, and the date that ownership was verified. Do not infer
that an account is official from its display name alone.

| Platform | Discussion object | Recommended access | Key limitation |
| --- | --- | --- | --- |
| [Bluesky](https://docs.bsky.app/docs/api/app-bsky-feed-get-feed) | Post, reply tree, quote post | Public API / user-visible capture | A reply tree is a snapshot; quote posts and reposts need separate collection. |
| [YouTube](https://developers.google.com/youtube/data/reference/rest/v3/commentThreads/list) | Video/channel comment thread and replies | YouTube Data API | Requires a project/API key; comments can be disabled; retrieve reply pages rather than assuming the first response is complete. |
| [Reddit](https://developers.reddit.com/docs/capabilities/server/reddit-api) | Submission, nested comment tree | Approved official developer access | API access and platform policies change; never bypass controls with unauthorised scraping. |
| [TikTok Research Tools](https://developers.tiktok.com/products/research-api/) | Video comments and replies | Approved Research Tools access | Available only to eligible public-interest researchers; access, quotas, and data fields are conditional. |
| Facebook / Instagram | Page post comments and replies | Explicit user-visible capture first; add approved Meta access only after a policy review | Do not assume public browser visibility means bulk/API collection is authorised. |
| X | Post replies, quotes, reposts | Explicit user-visible capture first; add an authorised API product only after confirming its scope | Reply ordering/ranking is not a chronological archive; preserve collection time and URL. |
| Telegram | Public channel posts; comments normally live in a linked discussion group | User-visible capture of public material only | A channel may have no linked discussion group; never collect private groups or DMs. |
| Mastodon | Public status and replies | Instance API where public and permitted | Federation is incomplete: a single instance is not a complete network view. |

For social comments, store a separate record rather than forcing them into an
article event:

```json
{
  "comment_id": "platform:comment-id",
  "parent_post_id": "platform:post-id",
  "parent_comment_id": null,
  "actor_id": "platform:account-id-or-null",
  "text": "visible comment text",
  "url": "permalink",
  "timestamp": "ISO-8601-or-null",
  "platform": "youtube",
  "source_id": "fi-yle-news",
  "collected_at": "ISO-8601"
}
```

Keep the publisher article/post and each comment's permalink linked. Never
present a small, ranked, moderated, deleted, or login-gated sample as the
opinion of an outlet's whole audience.

## Commenting and discussion map

**Interpretation:** “available” means the publisher documents a discussion
surface; it does not mean every article is open or that every submitted comment
is visible. “Per-page audit” means no stable, source-wide public interface was
verified in this research. Before building an adapter, open a current article,
record the observed state, and recheck it after any site redesign.

| Sources in inventory | Current comment/discussion model | Collection decision |
| --- | --- | --- |
| **Yle / Yle News** | **Verified first-party comments on selected material.** A user needs Yle ID and may use a name or pseudonym. Yle can use pre- or post-moderation, permits reporting, and may close a discussion or block a user. Its current [guidelines](https://yle.fi/aihe/a/20-10001658) state that AI assists moderation under human supervision. | Add an adapter only for comments currently visible to the user. Capture comment permalink/ID, displayed author handle, displayed time, parent relation, and article URL. Do not attempt to collect held, removed, or account-only material. |
| **Helsingin Sanomat, Ilta-Sanomat, Iltalehti, MTV Uutiset, STT, Hufvudstadsbladet, Aamulehti, Turun Sanomat, Kaleva, Verkkouutiset, Faktabaari** | **Per-page audit required.** Finnish publishers can enable, restrict, migrate, or remove first-party discussions independently. A historic report of a comment-policy change is not sufficient to describe current behaviour. | Do not create a site-wide comment crawler yet. At ingestion time, record `comments_observed: true/false/unknown`; add a source-specific adapter only after a current article and terms review. |
| **Finnish Government** | Public-feedback and social channels may exist, but they are not an article-comment dataset. | Treat releases as primary documents; collect public social discussion only under the relevant platform rule. |
| **LSM** | **Verified moderated discussion policy.** LSM's published rules cover its interactive platforms, social networks, messengers, and services; it may remove comments or close commenting for a particular publication/platform. See [LSM rules](https://rus.lsm.lv/pravila-polzovanija/LSM.LV). | Capture only comments displayed on a current, public page and treat missing comments as “unavailable”, not as zero discussion. Store language and edition (LV/RU/EN). |
| **Delfi Latvia, TVNET, Jauns.lv, Apollo.lv, TV3 Ziņas, Latvijas Avīze, Ir, nra.lv, Re:Baltica / Re:Check** | **Per-page audit required.** Some outlets may have a first-party or third-party discussion widget, but availability, account requirements, and moderation differ by article and can change. | No blanket collection. Audit a sample of current public articles for each source and record widget/provider, sign-in requirement, visible sort order, and moderation/deletion markers before implementation. |
| **Latvian Cabinet of Ministers, Latvian State Police** | Official releases are not a reliable article-comment corpus; audience discussion is generally on linked social accounts. | Treat the release as primary material and link separately collected public social replies only when the account is verified. |
| **Reuters, AP, AFP Fact Check, BBC, Deutsche Welle, France 24, Euronews, POLITICO Europe, EUobserver, Le Monde, Der Spiegel, RFE/RL, Bellingcat, EUvsDisinfo, European Commission** | **Per-page audit required / do not assume comments.** Many international news and institutional pages direct conversation to social platforms or use only selected features. Public comments may be absent, sign-in gated, geo-dependent, or unavailable in a given language edition. | Start with article/post metadata, then collect replies from an official linked social post where permitted. Build an on-site comment adapter only after a current source-specific audit. |
| **The Guardian** | **Verified selected first-party discussions.** Comments require a registered, signed-in user; the Guardian says it generally opens discussions on features, analysis, and Opinion rather than all news. Most threads are post-moderated, with premoderation in some situations. See [Community FAQs](https://www.theguardian.com/community-faqs). | Collect only visibly enabled public threads. Preserve `reply_to`, displayed username, time, recommendation count if displayed, and deletion/removal marker. Do not treat post-moderation as a guarantee that all collected text complies with policy. |
| **AP, Reuters U.S., NPR, PBS NewsHour, ABC, CBS, NBC, CNN, Fox News, MSNBC, NYT, WSJ, USA Today, Politico, Axios, The Hill, ProPublica, Newsmax, OAN, Breitbart, Daily Wire, Daily Caller, HuffPost, Mother Jones, NewsNation** | **Per-page audit required.** U.S. publishers use a mix of no on-site discussion, selected registered comments, third-party widgets, newsletters, and social-platform replies. NPR retired standard site comments in 2016, showing why a static site-wide assumption becomes stale. | Use official social posts as the initial discussion surface. For any first-party adapter, maintain a per-domain test fixture and a timestamped policy/HTML audit; do not use a generic “all U.S. articles have comments” extractor. |
| **FactCheck.org, PolitiFact, Snopes** | **Per-page audit required.** Treat fact-check pages primarily as verification/context records, not audience-opinion sources. | Save verdict, claim, evidence links, and update date. Only collect comments if a current visible, public thread has passed a privacy and terms review. |
| **Congress.gov, White House, Supreme Court** | Official documents and notices; they are not a uniform public comment system. | Ingest primary documents. Analyse public reaction only through separately verified social accounts or public consultation systems. |

### Comment data safeguards

- Public comments can still contain personal data. Store the minimum needed for
  analysis, do not collect contact details, and set a deletion/retention policy.
- Preserve moderation state when visible: `published`, `removed`, `closed`,
  `comments_disabled`, or `unknown`. Do not silently convert removed/hidden
  comments into live evidence.
- Capture page order (`top`, `new`, `relevance`) and collection time. Comment
  ranking can change the apparent narrative.
- Do not create accounts, evade a login wall, solve CAPTCHAs, or automate
  actions that alter engagement. The extension remains user-initiated and
  read-only.
- Make the UI state its coverage: for example, “42 visible comments captured;
  replies behind ‘load more’ were not collected.”
