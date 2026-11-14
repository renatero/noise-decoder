/**
 * Publisher domains researched in docs-local/news-monitoring-source-inventory.md.
 * This registry is routing metadata only: it is not a credibility or ideology
 * score and must never be used to label an article or its author.
 */
export const SOURCE_CATALOG = [
  ["yle.fi", "fi-yle-news", "Finland / Yle News"], ["hs.fi", "fi-helsingin-sanomat", "Finland / Helsingin Sanomat"],
  ["is.fi", "fi-ilta-sanomat", "Finland / Ilta-Sanomat"], ["iltalehti.fi", "fi-iltalehti", "Finland / Iltalehti"],
  ["mtvuutiset.fi", "fi-mtv-uutiset", "Finland / MTV Uutiset"], ["sttinfo.fi", "fi-stt", "Finland / STT"],
  ["hbl.fi", "fi-hbl", "Finland / Hufvudstadsbladet"], ["aamulehti.fi", "fi-aamulehti", "Finland / Aamulehti"],
  ["ts.fi", "fi-turun-sanomat", "Finland / Turun Sanomat"], ["kaleva.fi", "fi-kaleva", "Finland / Kaleva"],
  ["verkkouutiset.fi", "fi-verkkouutiset", "Finland / Verkkouutiset"], ["faktabaari.fi", "fi-faktabaari", "Finland / Faktabaari"],
  ["valtioneuvosto.fi", "fi-government", "Finland / Government"],
  ["lsm.lv", "lv-lsm", "Latvia / LSM"], ["delfi.lv", "lv-delfi", "Latvia / Delfi"],
  ["tvnet.lv", "lv-tvnet", "Latvia / TVNET"], ["jauns.lv", "lv-jauns", "Latvia / Jauns.lv"],
  ["apollo.lv", "lv-apollo", "Latvia / Apollo"], ["tv3.lv", "lv-tv3", "Latvia / TV3 Ziņas"],
  ["la.lv", "lv-latvijas-avize", "Latvia / Latvijas Avīze"], ["ir.lv", "lv-ir", "Latvia / Ir"],
  ["nra.lv", "lv-nra", "Latvia / nra.lv"], ["rebaltica.lv", "lv-rebaltica", "Latvia / Re:Baltica"],
  ["mk.gov.lv", "lv-cabinet", "Latvia / Cabinet of Ministers"], ["vp.gov.lv", "lv-state-police", "Latvia / State Police"],
  ["reuters.com", "eu-reuters", "Reuters"], ["apnews.com", "eu-ap", "Associated Press"],
  ["factcheck.afp.com", "eu-afp-fact-check", "AFP Fact Check"], ["bbc.com", "eu-bbc", "BBC"],
  ["dw.com", "eu-dw", "Deutsche Welle"], ["france24.com", "eu-france24", "France 24"],
  ["euronews.com", "eu-euronews", "Euronews"], ["politico.eu", "eu-politico", "POLITICO Europe"],
  ["euobserver.com", "eu-euobserver", "EUobserver"], ["theguardian.com", "eu-guardian", "The Guardian"],
  ["lemonde.fr", "eu-lemonde", "Le Monde"], ["spiegel.de", "eu-spiegel", "Der Spiegel"],
  ["rferl.org", "eu-rferl", "RFE/RL"], ["bellingcat.com", "eu-bellingcat", "Bellingcat"],
  ["euvsdisinfo.eu", "eu-euvsdisinfo", "EUvsDisinfo"], ["europa.eu", "eu-commission", "European Commission"],
  ["npr.org", "us-npr", "NPR"], ["pbs.org", "us-pbs-newshour", "PBS NewsHour"],
  ["abcnews.go.com", "us-abc", "ABC News"], ["cbsnews.com", "us-cbs", "CBS News"],
  ["nbcnews.com", "us-nbc", "NBC News"], ["cnn.com", "us-cnn", "CNN"], ["foxnews.com", "us-fox", "Fox News"],
  ["msnbc.com", "us-msnbc", "MSNBC"], ["nytimes.com", "us-nyt", "The New York Times"],
  ["wsj.com", "us-wsj", "The Wall Street Journal"], ["usatoday.com", "us-usa-today", "USA Today"],
  ["politico.com", "us-politico", "Politico"], ["axios.com", "us-axios", "Axios"],
  ["thehill.com", "us-the-hill", "The Hill"], ["propublica.org", "us-propublica", "ProPublica"],
  ["newsmax.com", "us-newsmax", "Newsmax"], ["oann.com", "us-oan", "One America News"],
  ["breitbart.com", "us-breitbart", "Breitbart"], ["dailywire.com", "us-daily-wire", "The Daily Wire"],
  ["dailycaller.com", "us-daily-caller", "The Daily Caller"], ["huffpost.com", "us-huffpost", "HuffPost"],
  ["motherjones.com", "us-mother-jones", "Mother Jones"], ["newsnationnow.com", "us-newsnation", "NewsNation"],
  ["factcheck.org", "us-factcheck-org", "FactCheck.org"], ["politifact.com", "us-politifact", "PolitiFact"],
  ["snopes.com", "us-snopes", "Snopes"], ["congress.gov", "us-congress", "Congress.gov"],
  ["whitehouse.gov", "us-white-house", "White House"], ["supremecourt.gov", "us-supreme-court", "Supreme Court"]
];

export function sourceForUrl(rawUrl) {
  try {
    const host = new URL(rawUrl).hostname.toLowerCase().replace(/^www\./, "");
    const match = SOURCE_CATALOG.find(([domain]) => host === domain || host.endsWith(`.${domain}`));
    return match ? { source_id: match[1], source_name: match[2], domain: match[0] } : null;
  } catch {
    return null;
  }
}

export function platformForUrl(rawUrl) {
  try {
    const host = new URL(rawUrl).hostname.toLowerCase();
    if (host.endsWith("x.com") || host.endsWith("twitter.com")) return "x";
    if (host.endsWith("bsky.app")) return "bluesky";
    if (host.endsWith("youtube.com") || host === "youtu.be") return "youtube";
    if (host.endsWith("reddit.com")) return "reddit";
    if (host.endsWith("tiktok.com")) return "tiktok";
    if (host.endsWith("instagram.com")) return "instagram";
    if (host.endsWith("facebook.com")) return "facebook";
    if (host === "t.me" || host.endsWith("telegram.org")) return "telegram";
    if (host.endsWith("threads.net")) return "threads";
    if (host.includes("mastodon")) return "mastodon";
    if (host.endsWith("ss.lv")) return "ss.lv";
    return sourceForUrl(rawUrl)?.source_id || host;
  } catch {
    return "unknown";
  }
}
