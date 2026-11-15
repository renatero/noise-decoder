"""Rebuild the dated research artifacts; no network access or application changes."""
from pathlib import Path
import csv
import html
import json

ROOT = Path(__file__).resolve().parent
DATE = '2026-11-14'
ROWS = []
HEADERS = [
    'Platform/source', 'API or tool name', 'Official website', 'Documentation URL',
    'API endpoint or GitHub repository', 'Free or paid', 'Free-tier limitations and quotas',
    'Authentication requirements', 'Real-time streaming availability', 'Historical search availability',
    'Search functionality', 'Data fields returned', 'Commercial-use restrictions', 'Ease of integration',
    'Availability/pricing checked UTC', 'Credit card requirement', 'Self-hosted server required',
    'Continuous collection feasibility', 'Multi-platform coverage', 'Storage and redistribution',
    'Additional evidence URLs', 'Recommendation',
]

def add(platform, name, website, docs, endpoint, price, quota, auth, stream, history,
        search, fields, commercial, ease, *, card='Not established by reviewed documentation; signup not tested',
        host='No; run your collector anywhere', continuous='Yes, subject to quota and permission',
        multi='No', storage='Source content remains subject to copyright and platform terms; no blanket redistribution grant.',
        evidence='See documentation URL in this row', recommendation='Conditional'):
    vals = [platform,name,website,docs,endpoint,price,quota,auth,stream,history,search,fields,
            commercial,ease,DATE,card,host,continuous,multi,storage,evidence,recommendation]
    assert len(vals) == len(HEADERS)
    ROWS.append(dict(zip(HEADERS, vals)))

add('Bluesky','Public AppView API','https://bsky.social',
    'https://bsky.network/docs/rate-limits/',
    'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts',
    'Free service','Generous public limits; no numeric AppView guarantee. Workspace probe: HTTP 403.',
    'Many public reads need no token; endpoint/host restrictions can apply','Use Jetstream separately',
    'Indexed posts; no complete-archive guarantee','Keyword, author, tag, language, since/until, cursor',
    'URI, CID, text, author, timestamps, reply/repost/like counts, embeds',
    'Public access does not license all user content; follow developer guidelines','Easy REST/JSON',
    card='None for public reads',evidence='https://bsky.network/docs/developer-guidelines/',
    recommendation='Core source; resolve search access from deployment environment')
add('Bluesky / AT Protocol','Jetstream','https://bsky.network',
    'https://bsky.network/docs/jetstream/',
    'https://github.com/bluesky-social/jetstream',
    'Free public service; open-source self-hosting','Public infrastructure has no SLA; replay availability depends on archive/server',
    'Public stream: no API key documented','Yes: JSON WebSocket, webhook forwarding tooling',
    'Replay and snapshots in current implementation; verify desired archive coverage',
    'Collections/accounts/event kinds; apply keyword matching locally',
    'DID, sequence, time, operation, collection, record key, record payload',
    'Software license does not grant rights to user posts','Moderate; persist sequence and handle deletes',
    card='None for public service',host='Optional',multi='AT Protocol applications, not closed social platforms',
    recommendation='Best open social streaming foundation')
add('Mastodon','Mastodon REST and Streaming APIs','https://joinmastodon.org',
    'https://docs.joinmastodon.org/methods/search/',
    'Instance: /api/v2/search; /api/v1/timelines/public; /api/v1/streaming',
    'Free; instance operated','Default 300 requests/5 minutes per account AND IP; operators may vary limits',
    'Some public REST reads anonymous; OAuth for full search/streaming','Yes: SSE/WebSocket; stream token required',
    'Only content indexed/retained by chosen instance','Accounts, hashtags, permitted full-text; offsets and filters',
    'Status HTML/text, account, time, media, tags, counts, URLs',
    'Instance policies and author rights apply; search visibility can be opt-in','Easy REST; moderate federation coverage',
    card='None for standard API',host='Optional',storage='Apply updates/deletes; instance access is not a license to republish all posts.',
    evidence='https://docs.joinmastodon.org/api/rate-limits/ | https://docs.joinmastodon.org/methods/streaming/',
    recommendation='Core source; explicitly label instance coverage')
add('Threads','Threads Keyword Search','https://developers.facebook.com/products/threads/',
    'https://developers.facebook.com/documentation/threads/keyword-search',
    'https://graph.threads.com/v1.0/keyword_search',
    'Free API with approval','2,200 queries/user/rolling 24 hours across apps; max 100 results/page; empty queries exempt',
    'OAuth; threads_basic and approved threads_keyword_search','No general public firehose',
    'since/until filters; no exhaustive archive promise','Keyword/tag; TOP/RECENT; media type; author_username; pagination',
    'ID, text, username, permalink, timestamp, media type, reply flags; owner excluded',
    'App review and Meta platform terms; unapproved search only searches own posts','Moderate; approval is main hurdle',
    recommendation='Best additional mainstream social candidate after review')
add('X / Twitter','X API v2','https://developer.x.com',
    'https://docs.x.com/x-api/getting-started/pricing',
    'https://api.x.com/2/tweets/search/recent',
    'Paid usage; not a sustainable free read API','Post reads $0.005/resource; promotional credits require qualifying purchase/card',
    'Developer app and bearer/OAuth token; funded credits','Paid filtered stream available',
    'Recent and full-archive products, subject to access and charges','Keywords, hashtags, users, dates, operators; pagination',
    'Post ID/text/time, author expansions, metrics and requested fields',
    'Developer agreement, redistribution/deletion obligations; commercial licensing applies','Easy REST; financially unsuitable for zero-cost scope',
    card='Payment required for sustained reads',continuous='Technically yes, paid',
    recommendation='Exclude from free ingestion budget')
add('Facebook','Graph API Pages','https://developers.facebook.com',
    'https://developers.facebook.com/docs/graph-api/reference/page/feed/',
    'https://graph.facebook.com/{version}/{page-id}/feed',
    'No general per-read price; restricted access','App/business-use-case limits; no universal free global-search quota',
    'Page/app tokens and permissions; PPCA review for non-managed public Pages',
    'Webhooks for authorized objects; no global stream','Accessible Page feed, subject to endpoint limits',
    'Known Page feeds/comments; no arbitrary Facebook-wide post search',
    'Post ID, message, time, permalink, permitted engagement/comments',
    'Permissioned use only; not a public-social firehose','Moderate/high review burden',
    evidence='https://developers.facebook.com/docs/graph-api/reference/page/',
    recommendation='Use only explicitly authorized Pages')
add('Instagram','Instagram Platform Hashtag Search','https://developers.facebook.com',
    'https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/hashtag-search',
    'Graph API: /ig_hashtag_search; /{hashtag-id}/recent_media; /top_media',
    'Free API with review','30 unique hashtags per professional account per rolling 7 days; fetching media also counts',
    'Business/Creator account, token, instagram_basic and Instagram Public Content Access approval',
    'No public hashtag firehose','Recent/top media, not complete historical archive',
    'Hashtags and own/authorized media; no unrestricted keyword search',
    'Media ID, caption, permalink, media type and permitted media fields',
    'Meta terms; Stories excluded; some media URLs withheld for rights/privacy','Moderate/high',
    recommendation='Narrow reviewed hashtag monitoring only')
add('Facebook / Instagram / Threads','Meta Content Library API','https://transparency.meta.com/researchtools/meta-content-library/',
    'https://developers.facebook.com/docs/content-library-and-api/content-library-api/overview',
    'Secure research environment; no unrestricted public ingest endpoint',
    'Free for approved researchers','Eligibility, research environment and project limits; no general startup entitlement',
    'Approved researcher/institution and secure environment','Not an external public firehose',
    'Historical public-content research within permitted coverage','Research search/filter/count tools',
    'Covered public posts/comments and metadata in cleanroom',
    'Restricted research purpose; API raw-data export/download prohibited','High; incompatible with normal external ingestion',
    host='Approved secure environment required',continuous='Only within approved research environment',multi='Yes, supported Meta datasets',
    storage='Raw API data cannot be exported into Noise Decoder. UI download exceptions do not grant API export rights.',
    evidence='https://developers.facebook.com/docs/content-library-and-api/support/faqs',
    recommendation='Research-only alternative; not centralized app backend')
add('Reddit','Reddit Data API / PRAW','https://www.reddit.com/dev/api/',
    'https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki',
    'https://oauth.reddit.com/search | https://github.com/praw-dev/praw',
    'Conditional free access; commercial contract may cost','Eligible approved free clients: 100 queries/minute per OAuth client; bulk export limited',
    'Approval, registered OAuth client, descriptive User-Agent','Polling; PRAW stream helpers are not network firehoses',
    'Search/listings constrained; no full historical comment archive','Subreddit, keyword, author, sort/time filters; after/before pagination',
    'Post/comment IDs, text, author, subreddit, score, time, permalink',
    'Commercial use requires permission/contract; academic research uses Reddit for Researchers',
    'Easy SDK after approval; access difficult',
    storage='Honor removals and data terms; no unrestricted bulk redistribution or model training.',
    evidence='https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data',
    recommendation='Approval-gated; not assume free commercial OSINT use')
add('TikTok','Research API; Display API alternative','https://developers.tiktok.com',
    'https://developers.tiktok.com/docs/en/research-api-faq',
    'https://open.tiktokapis.com/v2/research/video/query/',
    'Free approved research; not commercial listening','Research: 1,000 requests/day, up to 100,000 records/day for principal APIs; other endpoint quotas differ',
    'Approved research project; app client credentials/token','No; new videos may lag 48h, statistics up to 10 days',
    'Date-filtered archived research dataset','Keywords, hashtags, username, region/date and query filters',
    'Video ID, description, creator, time, counts; permitted comments/user metadata',
    'Not-for-profit qualified researchers; commercial users ineligible. Display API is consented-account access.',
    'Moderate technical work; high eligibility hurdle',
    recommendation='Exclude from general commercial free aggregator')
add('YouTube','YouTube Data API v3','https://developers.google.com/youtube',
    'https://developers.google.com/youtube/v3/docs/search/list',
    'https://www.googleapis.com/youtube/v3/search',
    'Free quota; extensions require approval','Current quota: 100 search.list calls/day separately; 10,000 units/day for other endpoints; each search page counts',
    'Google Cloud API key for public data; OAuth for user data','WebSub channel updates; no global keyword firehose',
    'Public video search with date bounds; comments via separate endpoints',
    'Keyword, channel, dates, region/location where supported; pageToken',
    'Video/channel IDs, title, description, timestamps, thumbnails; separate statistics/comments calls',
    'Developer policies constrain storage, derived metrics and use; not a blanket sentiment/mining license',
    'Easy REST and Python/Node SDKs',
    storage='Most non-authorized data must refresh/delete within 30 days; separate approved derived-metrics exceptions exist.',
    evidence='https://developers.google.com/youtube/data/determine_quota_cost | https://developers.google.com/youtube/terms/developer-policies | https://developers.google.com/youtube/terms/derived-metrics-policy',
    recommendation='Useful quota API; channel-first collection and policy review')
add('Telegram public channels','MTProto / TDLib / Telethon','https://core.telegram.org',
    'https://core.telegram.org/api',
    'https://github.com/tdlib/td | https://codeberg.org/Lonami/Telethon',
    'Client API free; global full-text search can require Stars','Dynamic FLOOD_WAIT; global channels.searchPosts has limited free slots then payment; no universal quota',
    'api_id/api_hash, phone login and user session','Yes: authorized account updates',
    'Accessible channel history; global search separately limited','Known-channel search/history; global hashtags/full-text under applicable entitlements',
    'Message ID/text/date, channel, entities, media references, permitted counts',
    'Client purpose/content terms restrict aggregation and AI use; public visibility alone is insufficient',
    'Moderate; protect session credentials',
    storage='Telegram licensing restricts indexing/aggregation for AI deployment without required consent; permission-gate this source.',
    evidence='https://core.telegram.org/method/channels.searchPosts | https://core.telegram.org/api/terms | https://telegram.org/tos/content-licensing',
    recommendation='Opt-in authorized channels only after intended-use clearance')
add('Telegram authorized channels','Telegram Bot API','https://core.telegram.org/bots',
    'https://core.telegram.org/bots/api',
    'https://api.telegram.org/bot<TOKEN>/getUpdates',
    'Free ordinary bot access','Not a global crawler; update retention/endpoint limits apply',
    'Bot token; bot must be added with sufficient channel access','Yes: webhooks or long polling channel_post',
    'No arbitrary channel history endpoint','Filter received updates locally; no global keyword search',
    'Message/channel IDs, text, time, entities, media references',
    'Bot/content terms and channel authorization apply','Easy REST/JSON',
    card='None for ordinary bot access',storage='Use only authorized bot purposes; Telegram content/AI restrictions still apply.',
    evidence='https://telegram.org/tos/content-licensing',recommendation='Suitable for explicit partner-channel integrations')
add('Discord public communities','Discord Bot API and Gateway','https://discord.com/developers',
    'https://docs.discord.com/developers/events/gateway',
    'https://discord.com/api/v10/channels/{channel.id}/messages | https://github.com/Rapptz/discord.py',
    'Free authorized bot API','Per-route/global limits; Message Content privileged intent/approval where applicable',
    'Bot token, guild installation, channel permissions and required intents','Yes: Gateway WebSocket',
    'Permitted channel message history only','No global community search API; filter authorized events locally',
    'Message, author/channel IDs, timestamp, attachments/content if intent permits',
    'No data scraping/mining or selling API data; model training requires express Discord permission',
    'Moderate; permissions/intents are essential',
    card='None for standard bot API',storage='Store only for permitted application purpose; no unrestricted public-data warehouse or resale.',
    evidence='https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy',
    recommendation='Opt-in community functionality, not broad OSINT harvesting')
add('LinkedIn','Community Management APIs','https://developer.linkedin.com',
    'https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview',
    'https://api.linkedin.com/rest/posts',
    'Restricted approved access; no general free listening API','Development/standard access and endpoint quotas; no universal public-search allowance',
    'Approved application, OAuth member/organization permissions','Product-specific events; no public firehose',
    'Authorized organizational content only','Organization/member permissions; no broad public-post keyword search',
    'Authorized posts, comments and social actions',
    'Restricted-use-case rules include social-feed uses; approved purpose required','High access barrier',
    continuous='Only approved use cases',
    evidence='https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases',
    recommendation='Exclude from general public monitoring scope')
add('Truth Social','Truth API licensed data service','https://truthsocial.com',
    'No public developer documentation verified',
    'No public free endpoint verified; vendor licensing',
    'Commercial subscription; no verified free tier','Quota and technical pricing not publicly verified',
    'Vendor contract/credentials','Licensed low-latency feed exists','Not publicly documented',
    'Selected-account feed; broad keyword search not verified','Licensed posts and vendor-defined metadata',
    'Contract required; automated database compilation restricted by site terms','Unknown until contracted',
    card='Paid contract',continuous='Paid service only',
    evidence='https://www.sec.gov/Archives/edgar/data/1849635/000143774926035884/djt20260930_10q.htm | https://help.truthsocial.com/legal/terms-of-service/',
    recommendation='Exclude from free scope; internal Mastodon endpoints are not official permission')
add('Lemmy','Lemmy API','https://join-lemmy.org',
    'https://join-lemmy.org/docs/contributors/04-api.html',
    'https://github.com/LemmyNet/lemmy-js-client',
    'Free instance API','Instance-specific rate limits and API version; match client/server versions',
    'Public reads often anonymous; bearer token for restricted operations','Poll HTTP; do not assume a universal current stream',
    'Content known to selected instance','Posts/comments/communities/users; search, sort, pagination',
    'Post/comment bodies, author/community, score, dates, URLs',
    'Instance policies and content licenses apply','Easy/moderate REST/TypeScript',
    card='None for standard public reads',host='Optional',recommendation='Good federated discussion source')
add('PeerTube','PeerTube REST API','https://joinpeertube.org',
    'https://docs.joinpeertube.org/api-rest-reference/api.html',
    'Instance: /api/v1/search/videos | https://github.com/Chocobozzz/PeerTube',
    'Free instance API','Operator-specific limits; federation does not imply full network coverage',
    'Public metadata often anonymous; OAuth for protected actions','Feeds/polling; no universal public firehose',
    'Videos retained/indexed by instance','Keywords, tags, channels, dates and pagination',
    'Video UUID, name, description, account/channel, dates, tags, license, counts',
    'Per-video licenses and instance terms apply','Easy REST/JSON',
    card='None for standard public reads',host='Optional',storage='Use the video license field; API access alone does not authorize media redistribution.',
    recommendation='Useful open video alternative')
add('Nostr','Relay protocol (NIP-01 / NIP-50)','https://nostr.com',
    'https://github.com/nostr-protocol/nips/blob/master/01.md',
    'https://github.com/nostr-protocol/nips',
    'Free public relays exist; some relays paid','Relay-specific connections, retention, filters and limits',
    'Some relays anonymous reads; others NIP-42 authentication/payment','Yes: WebSocket subscriptions',
    'Only records retained by each relay','Author, kind, hashtag, since/until; full-text only where NIP-50 supported',
    'Event ID, public key, created_at, kind, tags, content, signature',
    'Open protocol does not waive relay rules or content copyright','Moderate; verify signatures and deduplicate relays',
    card='None on selected free relays',host='Optional',multi='Nostr applications',
    recommendation='Good open social supplement; variable coverage')

add('Global news','GDELT DOC 2.0 and bulk datasets','https://www.gdeltproject.org',
    'https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/',
    'https://api.gdeltproject.org/api/v2/doc/doc | https://data.gdeltproject.org/gdeltv2/lastupdate.txt',
    'Free API/data; optional BigQuery compute may cost','Live DOC probe returned 429, asks <=1 request/5s; ArtList bounded, not exhaustive pagination',
    'No key for public API/bulk','15-minute bulk updates; poll DOC; not a guaranteed stream',
    'DOC horizon uncertain: original 3 months, 2018 announcement 1 year; validate operationally. Event archive is separate.',
    'Boolean keywords, domain, language/country, time; split bounded windows carefully',
    'Article URLs/titles, seen dates, domains, language/country; events/GKG separate schemas',
    'GDELT data open; underlying publisher articles retain copyright','Easy DOC JSON; moderate bulk pipeline',
    card='None for API/bulk',multi='Many news publishers',storage='Store GDELT metadata with provenance; do not infer a full-text republication license.',
    evidence='https://www.gdeltproject.org/data.html | https://blog.gdeltproject.org/doc-geo-2-0-api-updates-full-year-searching-and-more/',
    recommendation='Broad free news foundation with throttling/bulk fallback')
add('Global news research','Media Cloud Search API','https://www.mediacloud.org',
    'https://www.mediacloud.org/documentation/search-api-guide',
    'https://github.com/mediacloud/api-client',
    'Free quota API','4,000 requests/week; some endpoints 2/minute; no full article text',
    'Account/API key','Polling; no public event stream','Archive from when sources were tracked',
    'Keywords, source/collection, dates; story lists and aggregate counts',
    'Story URL/title/date/source and aggregate analytics',
    'Lawful use subject to terms; no sale/sublicensing of service/access; built for research/journalism',
    'Easy Python client',multi='Many news publishers',
    storage='Metadata/aggregate outputs usable within terms; full text withheld for copyright reasons.',
    evidence='https://www.mediacloud.org/documentation/faqs | https://www.mediacloud.org/legal/media-cloud-terms-of-use',
    recommendation='Best free quota-based news research complement')
add('Publisher news / blogs / institutions','Native RSS / Atom / JSON Feed','https://www.rssboard.org/rss-specification',
    'https://feedparser.readthedocs.io/en/latest/',
    'Publisher feed URLs; e.g. https://feeds.bbci.co.uk/news/world/rss.xml',
    'Usually free access','Publisher-specific polling/terms; often only latest entries; use ETag/Last-Modified',
    'Usually none; subscription feeds may require credentials','WebSub on supporting feeds; otherwise poll',
    'Usually latest feed window; retain allowed history yourself','Feed/category selection; local text/date filters; no universal server search',
    'GUID, title, link, published/updated, author, summary/content, enclosures',
    'Each publisher has separate syndication/commercial terms','Very easy: feedparser or Node RSS parser',
    card='None for public feeds',multi='Thousands of news/blog/institution publishers',
    storage='Keep attribution and links; feed availability is not permission to republish full text or images.',
    recommendation='Primary low-cost ingestion layer')
add('Google News','Google News RSS search (undocumented)','https://news.google.com',
    'No supported public News RSS search API contract located',
    'https://news.google.com/rss/search?q=climate&hl=en-US&gl=US&ceid=US:en',
    'Public RSS currently accessible; unofficial integration','No published quota/SLA; live XML probe succeeded; behavior can change',
    'None for tested RSS URL','No; poll','Recent results; date operators do not guarantee archive completeness',
    'Observed keyword/language/region feed behavior; no guaranteed pagination',
    'RSS title/link/date/source/description; links can redirect',
    'Google terms and publisher rights; not equivalent to licensed official News API','Easy technically, fragile contract',
    card='None for public URL',multi='Many news publishers',
    evidence='https://policies.google.com/terms',recommendation='Optional discovery supplement; not reliability foundation')
add('Bing News','Bing News Search API (retired)','https://www.microsoft.com/bing',
    'https://learn.microsoft.com/lifecycle/announcements/bing-search-api-retirement',
    'Legacy api.bing.microsoft.com/v7.0/news/search',
    'Discontinued','Retired August 11, 2025; not a free option','N/A','N/A','N/A','N/A','N/A',
    'Replacement grounding products are different paid services','Do not integrate',card='N/A',
    host='N/A',continuous='No',multi='Previously many publishers',storage='N/A',recommendation='Exclude')
add('NewsAPI.org','NewsAPI Developer','https://newsapi.org',
    'https://newsapi.org/docs',
    'https://newsapi.org/v2/everything',
    'Free development tier; paid production','100 requests/day; 24-hour delay; last month',
    'API key','No free real-time stream','Last month on free tier',
    'Keyword, source/domain, language, date, pagination','Title, description, URL, author, source, time, truncated content',
    'Free plan is development/testing only, including no internal production or staging','Easy REST',
    continuous='Development only on free tier',multi='Many news publishers',
    evidence='https://newsapi.org/pricing',recommendation='Prototype only; exclude deployed free stack')
add('GNews.io (not Google)','GNews Free','https://gnews.io',
    'https://docs.gnews.io',
    'https://gnews.io/api/v4/search',
    'Recurring free tier; paid upgrades','100 requests/day; 10 articles/request; 12h delay; 30-day history; content truncated',
    'API key','No free stream','30 days','Keywords, language/country, dates; plan-limited results',
    'Title, description, URL, source, image URL, publishedAt, short content',
    'Free noncommercial; browser CORS limited to localhost','Easy REST',
    card='No card for free plan',multi='Many news publishers',evidence='https://gnews.io/pricing',
    recommendation='Noncommercial prototype; not Google News API')
add('NewsData.io','NewsData Free','https://newsdata.io',
    'https://newsdata.io/documentation',
    'https://newsdata.io/api/1/latest',
    'Recurring free tier','200 credits/day; 1–10 articles/credit; 12h delay; past 48h',
    'API key','Free real-time entitlement not established; do not infer from pricing icons',
    '48h on free plan','Keyword, country, language, category and page cursor',
    'Article ID/title/link, source, publication date, description and available metadata',
    'Free plan described for testing/personal use; commercial permission not established','Easy REST',
    multi='Many news publishers',evidence='https://newsdata.io/pricing',recommendation='Prototype shortlist only')
add('mediastack','mediastack Free','https://mediastack.com',
    'https://docs.apilayer.com/mediastack',
    'https://api.mediastack.com/v1/news',
    'Recurring free tier','100 requests/month; delayed news; HTTPS included; historical paid',
    'access_key','No free live stream','Not on free tier','Keywords, sources, countries, language, category, pagination',
    'Author, title, description, URL/image, source, category, language/country, time',
    'Free noncommercial','Easy REST; very low free capacity',multi='Many news publishers',
    evidence='https://mediastack.com/pricing',recommendation='Too small for continuous monitoring')
add('TheNewsAPI','TheNewsAPI Free','https://www.thenewsapi.com',
    'https://www.thenewsapi.com/documentation',
    'https://api.thenewsapi.com/v1/news/all',
    'Recurring free tier','100 requests/day; 3 articles/request; real-time and historical access listed',
    'API token','Current HTTP results; not a verified push stream','Included; horizon not established',
    'Keyword, source, language, category, date, pagination','UUID, title, snippet, URL, source, image URL, time, categories',
    'Commercial storage/redistribution entitlement not established by pricing page','Easy REST',
    multi='Many news publishers',evidence='https://www.thenewsapi.com/pricing',
    recommendation='Small real-time sample; confirm usage terms')
add('The Guardian','Open Platform Developer','https://open-platform.theguardian.com',
    'https://open-platform.theguardian.com/documentation/',
    'https://content.guardianapis.com/search',
    'Free noncommercial developer tier','500 requests/day; 1 request/second',
    'API key','Poll; no public stream','Guardian archive with date filters',
    'Keywords, section, tags, dates, pagination; request fields','Article ID/title/URL, section, time, tags, optional article text',
    'Commercial use requires license, including commercial text mining/sentiment without republishing','Very easy REST',
    storage='Use only within developer license; preserve attribution; content is not public domain.',
    evidence='https://open-platform.theguardian.com/access/',recommendation='Excellent noncommercial single-publisher API')
add('Currents','Currents Free','https://currentsapi.services',
    'https://currentsapi.services/en/docs/',
    'https://api.currentsapi.services/v1/search',
    'Recurring free tier','250 requests/day; 20 results/request; 30-day history; partial content',
    'API key','Poll; no free stream verified','30 days','Keywords, language, category, dates and pagination',
    'ID, title, description, URL, author, image, language, category, date',
    'Commercial redistribution rights not established by pricing page','Easy REST',
    card='No card stated',multi='Many news publishers',evidence='https://currentsapi.services/en/product/price',
    recommendation='Generous prototype quota; confirm production terms')
add('World News API','World News API Free','https://worldnewsapi.com',
    'https://worldnewsapi.com/docs/',
    'https://api.worldnewsapi.com/search-news',
    'Recurring free tier','50 points/day, not 50 calls; variable endpoint costs; 1 request/s; 1 concurrent request',
    'API key','Poll; no free stream verified','Last month on free plan',
    'Text, entities, location, language, country, date; endpoint-dependent pagination',
    'Title, text/summary where available, URL, publication time, language, entities',
    'Free backlink requirement; commercial/raw-content redistribution not established','Easy REST; budget points carefully',
    multi='Many news publishers',evidence='https://worldnewsapi.com/pricing/',recommendation='Small enrichment/discovery workload')
add('Financial news','Marketaux Free','https://www.marketaux.com',
    'https://www.marketaux.com/documentation',
    'https://api.marketaux.com/v1/news/all',
    'Recurring free tier','100 requests/day; 3 articles/request; instant news listed',
    'API token','Poll; no free push verified','Date filters; free archive horizon unverified',
    'Keywords, symbols/entities, countries/language, date, pagination',
    'Title, description, URL/time/source, financial entities and sentiment metadata',
    'Pricing page does not settle content resale/storage permission','Easy REST',
    multi='Financial news publishers',evidence='https://www.marketaux.com/pricing',recommendation='Niche finance supplement')

add('Hacker News','Official HN Firebase API','https://news.ycombinator.com',
    'https://github.com/HackerNews/API',
    'https://hacker-news.firebaseio.com/v0/newstories.json',
    'Free public API','No published rate limit in official README; still cache and avoid excessive requests',
    'None','Firebase change subscription/SSE patterns; updates endpoint',
    'Items accessible by ID; not a keyword archive search API','Story lists, item/user lookups; search locally or via Algolia',
    'ID, type, by, time, title/text, URL, score, parent/kids',
    'User content rights and HN terms apply','Very easy JSON REST',
    card='None',recommendation='Core free discussion source')
add('Hacker News','Algolia HN Search','https://hn.algolia.com',
    'https://hn.algolia.com/api',
    'https://hn.algolia.com/api/v1/search_by_date',
    'Free hosted search','No contractual quota/SLA established; source repository archived, live API probe succeeded',
    'None for public endpoint','No; poll','Indexed HN history, not guaranteed complete',
    'Keyword, author/tags, date/score numeric filters; page/hitsPerPage',
    'Object ID, title, URL, author, created time, points, comment text/highlights',
    'Hosted service/content terms; do not infer ownership of posts','Very easy REST/JSON',
    card='None',evidence='https://github.com/algolia/hn-search',recommendation='Useful HN search; keep official API fallback')
add('Stack Exchange / Stack Overflow','Stack Exchange API v2.3','https://api.stackexchange.com',
    'https://api.stackexchange.com/docs',
    'https://api.stackexchange.com/2.3/search/advanced',
    'Free quota API','Default 10,000/day with registered key; quota scope depends on auth; honor backoff; >30/s is abusive',
    'Public reads possible without key at lower allowance; register key; OAuth for user actions',
    'Poll; repeat identical queries no faster than 1 minute','Public questions/answers and comments with date filters',
    'Site, keyword/title, tags, dates, sort, pagination','Question/answer IDs, title/body via filters, owner, score, tags, time, links',
    'CC BY-SA version/attribution requirements for reused contributions','Easy REST',
    multi='Stack Exchange communities',storage='Attribution and applicable CC BY-SA obligations for reused content; preserve source/license metadata.',
    evidence='https://api.stackexchange.com/docs/throttle',recommendation='Best specialist technical discussion API')
add('Independent sites / blogs','WordPress REST API','https://wordpress.org',
    'https://developer.wordpress.org/rest-api/reference/posts/',
    'Publisher: /wp-json/wp/v2/posts',
    'Free where publisher enables public reads','Publisher hosting/rate rules; no universal allowance',
    'Public posts often anonymous; auth for restricted data','Poll; publisher plugins may provide webhooks',
    'Public posts retained by site','Search, author, tags/categories, after/before, pages',
    'ID, slug, title, rendered content/excerpt, dates, author ID, link',
    'Publisher license controls; WordPress GPL is not content license','Very easy REST/JSON',
    card='None for public endpoints',multi='Many independent WordPress publishers',recommendation='Add allowlisted publisher endpoints')
add('Forums','Discourse API','https://www.discourse.org',
    'https://docs.discourse.org/',
    'Forum: /search.json; /t/{topic-id}.json',
    'Free where forum permits','Site-specific limits and visibility; many admin APIs require keys',
    'Public reads may be anonymous; scoped API key for authorized use','Admin-configured webhooks; otherwise polling',
    'Site-retained public topics','Text, category/user/date where allowed; pagination','Topic/post IDs, title/body, user, time, tags, reply counts',
    'Forum policy and content license; no permission to access private categories','Easy/moderate',
    card='None for public reads',multi='Many Discourse forums',recommendation='Partner/allowlisted forums')
add('Wikipedia / Wikimedia','EventStreams and MediaWiki APIs','https://www.wikimedia.org',
    'https://wikitech.wikimedia.org/wiki/Event_Platform/EventStreams',
    'https://stream.wikimedia.org/v2/stream/recentchange',
    'Free public infrastructure','Follow User-Agent/rate policies; stream replay retention is bounded',
    'No key for public streams','Yes: SSE','Separate revisions/APIs/dumps; stream is not unlimited archive',
    'Filter wiki/page/user/events locally; separate MediaWiki search','Revision/page IDs, title, user, timestamp, change metadata',
    'Applicable Wikimedia licenses, attribution and privacy rules','Easy SSE plus JSON REST',
    card='None',multi='Wikimedia wikis',storage='Page text generally CC BY-SA; structured datasets can have different licenses.',
    recommendation='Useful emerging-topic signal, not a social-post feed')
add('US government policy','Federal Register API','https://www.federalregister.gov',
    'https://www.federalregister.gov/developers/documentation/api/v1',
    'https://www.federalregister.gov/api/v1/documents.json',
    'Free public API','No numeric quota verified; polite pagination/cache',
    'None','Poll daily/current documents','Historical documents with publication dates',
    'Keyword, agency, type, dates and pagination','Document number, title, agency, dates, abstract, HTML/PDF URLs',
    'Government documents generally reusable; exceptions/third-party materials possible','Very easy REST/JSON',
    card='None',multi='US agencies',storage='Preserve official document/PDF link; API web rendering is not the official legal edition.',
    recommendation='High-quality primary-source addition')
add('US company filings','SEC EDGAR data APIs','https://www.sec.gov',
    'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',
    'https://data.sec.gov/submissions/CIK{10-digit-CIK}.json',
    'Free public API','SEC fair-access policy; identify application/contact; cache and avoid bursts',
    'No API key; descriptive User-Agent','Submissions updated throughout day; poll; bulk nightly',
    'Submission history and separate older files','Company/CIK, filing type/date locally; not this endpoint as global full-text search',
    'Company, accession, form, filing/report date, primary-document references',
    'Filing availability does not make all corporate exhibits public-domain','Easy REST/JSON',
    card='None',multi='Public companies/filers',recommendation='Strong official corporate-news signal')
add('Humanitarian news / institutions','ReliefWeb API v2','https://reliefweb.int',
    'https://apidoc.reliefweb.int/',
    'https://api.reliefweb.int/v2/reports?appname=YOUR-APPROVED-APPNAME',
    'Free approved application access','Pre-approved appname mandatory; endpoint limits apply; numeric allowance not established here',
    'Approved appname; no secret read key. Publishing separately requires credentials.',
    'Poll','Historical report archive','Keyword, source, country, disaster, date, fields, offset/limit',
    'Report ID/title/body, dates, countries, sources, URL, file metadata',
    'Original source rights and ReliefWeb terms; attribution required where applicable','Easy REST after appname approval',
    multi='UN/NGO/government sources',storage='Check original report licensing; ReliefWeb explicitly warns against assuming reuse rights.',
    recommendation='Excellent international institutional aggregation')
add('Natural-hazard news','USGS Earthquake Catalog / GeoJSON feeds','https://earthquake.usgs.gov',
    'https://earthquake.usgs.gov/fdsnws/event/1/',
    'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson',
    'Free public API/feed','Use real-time GeoJSON feeds for automation; query endpoint has result bounds',
    'None','Near-real-time feed polling','Historical earthquake catalog',
    'Date, magnitude, location/radius/bounds; query limit/offset','Event ID, magnitude, place, time, geometry, URL, status',
    'USGS data generally open; third-party exceptions/attribution still matter','Very easy GeoJSON',
    card='None',recommendation='Useful event corroboration; not general news')
add('Weather / emergency alerts','US National Weather Service API','https://www.weather.gov',
    'https://www.weather.gov/documentation/services-web-api',
    'https://api.weather.gov/alerts/active',
    'Free public API','Undisclosed reasonable rate limits; cache responses',
    'Descriptive User-Agent; no API key currently','Poll alerts; not global social stream',
    'Limited alert history; use archives for long term','Area, event, severity, zone and location filters',
    'Alert ID, headline, severity, urgency, times, areas, geometry, instructions',
    'US government data generally open; preserve notices and provenance','Easy GeoJSON/JSON-LD',
    card='None',recommendation='Useful official incident signal')

add('Web / news discovery','Tavily Search','https://www.tavily.com',
    'https://docs.tavily.com/documentation/api-reference/endpoint/search',
    'https://api.tavily.com/search',
    'Recurring free credits; paid beyond enabled limits','1,000 credits/month; basic search 1, advanced 2; crawling/extraction separately metered',
    'API key','No firehose','Date/time filters over index, not complete archive',
    'Keyword, news/general topic, country/language, dates, included/excluded domains; bounded results',
    'Title, URL, content snippet, score and optional date/raw content',
    'API/service license and original publishers rights apply; no social account access entitlement','Very easy REST/Python/Node',
    card='No card for free tier',multi='Indexed web/news sources',
    evidence='https://docs.tavily.com/documentation/api-credits',recommendation='Good supplemental discovery; not continuous bulk ingestion')
add('Web / news discovery','Brave Search API','https://brave.com/search/api/',
    'https://api-dashboard.search.brave.com/documentation/quickstart',
    'https://api.search.brave.com/res/v1/news/search',
    'Paid API with conditional recurring credits','Current page advertises up to $20 free monthly calls; eligibility/activation must be confirmed',
    'Subscription token and billing activation','No public firehose','Search index; date filters are not complete archive',
    'Keyword, country/language, freshness and bounded pagination','Title, URL, snippet, age, source and thumbnails',
    'Plan rights govern storage/use; underlying content rights remain','Easy REST',
    card='Credit card required in onboarding docs',multi='Web and news indexes',
    recommendation='Not a no-card free recommendation')
add('RSS conversion','rss2json','https://rss2json.com',
    'https://rss2json.com/docs',
    'https://api.rss2json.com/v1/api.json',
    'Free access plus plans; exact current allowance unverified','Default 10 feed items; key required for count/order controls; no verified current free request quota',
    'Optional API key for basic call','Poll cached feed','Feed window only','Convert known feed; order/count; no cross-platform global search',
    'Feed title/link and item title/link/date/author/content/enclosures',
    'Conversion service does not grant publisher redistribution rights','Very easy REST/JSON',
    multi='Any supported accessible feed',evidence='https://rss2json.com/terms',recommendation='Convenience only; self-host parsing avoids dependency')
add('Automation / third-party collectors','Apify platform','https://apify.com',
    'https://docs.apify.com/api/v2',
    'https://api.apify.com/v2',
    'Recurring free credits; metered paid upgrades','Free $5/month platform/Actor credit; actor, compute, proxy and storage costs vary',
    'Account/API token','Schedules/webhooks for runs; not native social firehose','Actor/upstream dependent',
    'Actor dependent; no universal search entitlement','JSON datasets with Actor-specific schemas',
    'Actors may scrape unofficial endpoints; customer must have source permission','Easy orchestration, variable reliability',
    card='No card for free plan',multi='Many Actors, permissions differ',
    evidence='https://apify.com/pricing',recommendation='Use only authorized APIs/feeds; not a free social-data license')

def oss(platform, name, repo, docs, license_, role, search, fields, caveat, *, stream='Polling/scheduling; upstream dependent',
        history='Only collected history or upstream access', ease='Moderate; Docker/server operations', recommendation='Evaluate'):
    add(platform,name,'https://github.com/'+repo,docs,'https://github.com/'+repo,
        'Free self-hosted software; infrastructure/upstreams may cost',
        'No software metering; all upstream quotas still apply',
        'Local credentials plus upstream keys/tokens where needed',stream,history,search,fields,
        license_+' software; '+caveat,ease,
        card='No card for software; upstream varies',host='Yes for continuous self-hosted service',
        multi=role,storage='Software license covers code, not collected content. Apply each upstream retention/reuse policy.',
        recommendation=recommendation)

oss('Multi-source listening','Harken','VladUZH/harken','https://github.com/VladUZH/harken#readme','MIT',
    'Bluesky, HN, RSS, Mastodon; optional Reddit, X, YouTube, Stack Overflow',
    'Queries and unified collected mentions','Normalized mention text, source, author, URL, time, score',
    'Reddit adapter uses OAuth; X adapter uses paid official API; source approval still needed',
    recommendation='Best lightweight multi-platform prototype candidate; not production-certified')
oss('Multi-source listening','OpenMagpie','obris-dev/openmagpie','https://github.com/obris-dev/openmagpie#readme',
    'Apache-2.0 base with extra terms/ee exception; inspect LICENSE',
    'HN/RSS plus X, Reddit, YouTube connectors',
    'Feeds, queries and optional semantic filters','Unified feed events and webhook payloads',
    'Inspected X uses Twikit, YouTube yt-dlp, Reddit anonymous RSS: not equivalent to approved official APIs',
    recommendation='Do not adopt unofficial social connectors for this objective')
oss('Multi-source OSINT','Orthanc','beanssec/Orthanc','https://github.com/beanssec/Orthanc#readme','MIT',
    'RSS, social/institutional connectors, maps and analysis',
    'Unified filters/entity/event analysis','Collected items, entities, time/geography and source metadata',
    'Connector claims not live validated; enable only sources with established permission',
    recommendation='Feature-rich candidate; heavier and less validated than existing app')
oss('RSS aggregation','Miniflux','miniflux/v2','https://miniflux.app/docs/api.html','Apache-2.0',
    'RSS/Atom/JSON feeds from many publishers','Local entry filters/search/pagination','Entry ID/title/content/URL/date/feed',
    'Feed publisher rights still apply',ease='Easy Docker + PostgreSQL; X-Auth-Token JSON API',
    recommendation='Best feed backend for Noise Decoder')
oss('RSS aggregation','FreshRSS','FreshRSS/FreshRSS','https://freshrss.github.io/FreshRSS/en/','AGPL-3.0',
    'Many publisher feeds','Search/tags/filters and client API','Feed entries, categories, states and metadata',
    'Comply with AGPL obligations for modifications/network use',stream='WebSub on compatible feeds; scheduled polling otherwise',
    recommendation='Best ready-made multi-user feed UI')
oss('Feed generation','RSSHub','DIYgod/RSSHub','https://github.com/DIYgod/RSSHub#readme','AGPL-3.0',
    'Many site-specific routes','Route-specific filters; not universal search','RSS/Atom entries with route-dependent fields',
    'Many routes scrape or need cookies; route availability is not authorization',
    recommendation='Only explicitly permitted routes; prefer native publisher feeds')
oss('Feed generation','RSS-Bridge','RSS-Bridge/rss-bridge','https://rss-bridge.github.io/rss-bridge/index.html','Unlicense',
    'Many websites and feed utilities','Bridge filters/merging; route dependent','Generated feed items, output format dependent',
    'Website extraction requires source permission; public instances have no SLA',
    recommendation='Fallback for authorized sites lacking feeds')
oss('Automation','Huginn','huginn/huginn','https://github.com/huginn/huginn#readme','MIT',
    'Feeds, HTTP APIs, webhooks and event agents','Configured keyword/condition filters','Agent events; JSON endpoints/feeds',
    'Old social agents do not bypass current access costs',stream='Webhooks plus scheduled agents',
    recommendation='Best general self-hosted scheduling/alert workflow')
oss('Multi-engine search','SearXNG','searxng/searxng','https://docs.searxng.org/dev/search_api.html','AGPL-3.0',
    'Web/news engines; engine-dependent social discovery','Query/categories/engines/time-range; JSON must be enabled','Result title/URL/snippet/source',
    'Some engines use scraping; upstream blocking/terms remain; no licensed social firehose',
    history='Search-engine indexed pages, no guaranteed archive',recommendation='Discovery only; use permitted engines')
oss('Page monitoring','changedetection.io','dgtlmoon/changedetection.io','https://github.com/dgtlmoon/changedetection.io#readme','Apache-2.0',
    'Known public/authorized webpages','Watch URLs and text changes','Change snapshots/diffs and alerts',
    'Use only permitted pages; not a global keyword search API',recommendation='Institutional pages without RSS, subject to permission')
oss('OSINT enrichment','SpiderFoot','smicallef/spiderfoot','https://github.com/smicallef/spiderfoot#readme','MIT',
    'Many public/third-party lookup modules','Entity/domain/identity enrichment','Module-specific evidence/entities',
    'Some modules need paid APIs; identity OSINT is not continuous news aggregation',
    recommendation='Optional enrichment, not primary collection backend')
oss('Federated social client','CrispDeck','CrispStrobe/CrispDeck','https://github.com/CrispStrobe/CrispDeck#readme','AGPL-3.0',
    'Bluesky and Mastodon','Column/keyword monitoring','Social posts and UI columns',
    'Client workflow; not a turnkey multi-platform archival API',stream='Jetstream and Mastodon streaming',
    recommendation='Useful analyst UI reference')

def esc(value):
    return html.escape(str(value), quote=True)

def linkify(value):
    import re
    pieces = re.split(r'(https?://[^\s|<>]+)', str(value))
    return ''.join('<a href="'+esc(p)+'">'+esc(p)+'</a>' if p.startswith(('http://','https://')) else esc(p) for p in pieces)

def main():
    with (ROOT/'comparison.csv').open('w',newline='',encoding='utf-8-sig') as out:
        writer=csv.DictWriter(out,fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(ROWS)
    (ROOT/'comparison.json').write_text(json.dumps(ROWS,indent=2,ensure_ascii=False)+'\n')
    template=(ROOT/'report-template.html').read_text()
    matrix='<table id="matrix"><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in HEADERS)+'</tr></thead><tbody>'
    for i,row in enumerate(ROWS):
        matrix+='<tr id="source-'+str(i+1)+'">'+''.join('<td>'+linkify(row[h])+'</td>' for h in HEADERS)+'</tr>'
    matrix+='</tbody></table>'
    audit=json.loads((ROOT/'github-audit.json').read_text())
    audit=[r for r in audit if r.get('url') and r.get('pushed_at')]
    git='<table><thead><tr><th>Repository</th><th>Last push UTC</th><th>Archived</th><th>Reported license</th></tr></thead><tbody>'
    for r in audit:
        git+='<tr><td><a href="'+esc(r['url'])+'">'+esc(r['repository'])+'</a></td><td>'+esc(r['pushed_at'])+'</td><td>'+esc(r['archived'])+'</td><td>'+esc(r.get('license','Not detected'))+'</td></tr>'
    git+='</tbody></table>'
    probes=json.loads((ROOT/'live-probes.json').read_text())
    live='<table><thead><tr><th>Source</th><th>HTTP status</th><th>Observed result</th></tr></thead><tbody>'
    for r in probes:
        result=r.get('response_shape','Failed; see raw probe log')
        live+='<tr><td>'+esc(r['source'])+'</td><td>'+esc(r.get('status','Error'))+'</td><td>'+esc(result)+'</td></tr>'
    live+='</tbody></table>'
    output=template.replace('{{MATRIX}}',matrix).replace('{{GITHUB}}',git).replace('{{PROBES}}',live).replace('{{COUNT}}',str(len(ROWS)))
    output=output.replace('{{PYTHON}}',esc((ROOT/'integration_examples.py').read_text()))
    (ROOT/'report.html').write_text(output)
    print(f'Wrote report.html, comparison.csv and comparison.json: {len(ROWS)} rows, {len(HEADERS)} columns; {len(audit)} audited GitHub repositories.')

if __name__=='__main__':
    main()
