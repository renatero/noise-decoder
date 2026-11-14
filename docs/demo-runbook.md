# Coordination Radar demo runbook

1. Load the Chrome extension and set its dashboard URL.
2. Right-click a page, link, or selected text and choose **Investigate with
   Coordination Radar**. The dashboard receives a reference only; no content
   has been collected or analysed at this point.
3. Choose **Synthetic coordinated scenario** and investigate. Explain the
   synthetic banner, candidate status, recurring URL groups, and graph edge
   evidence.
4. Choose **Synthetic benign scenario** and investigate. Explain why the
   one-off breaking-news response remains inconclusive.
5. Optionally run a bounded public Bluesky phrase search. If unavailable, use
   **Offline Bluesky snapshot**.
6. Show limitations: public-search coverage is bounded, relationship evidence
   does not establish bot identity, coordination, propaganda intent, or any
   claim about a real person.

Before presenting, verify `/healthz`, the two synthetic scenarios, the offline
snapshot, and the extension dashboard handoff. Freeze features after this
check; fix only demo-blocking defects.
