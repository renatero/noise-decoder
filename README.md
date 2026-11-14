# noise-decoder
hostinger challenge junction 2026

## Behavioral coordination detection: time-window signal

The first time-based signal looks for accounts publishing posts that are already related by a shared canonical URL or similar content. It identifies candidate bursts for review; timing and content similarity alone do not establish coordination.

### Algorithm outline

1. Start from the candidate post groups produced by the shared-URL and near-duplicate matcher. Retain each pair's matching reason and evidence.
2. Parse each post's published timestamp as a UTC instant. Exclude posts with missing or invalid timestamps from the time-window calculation and report the excluded count. Do not substitute extraction time for publication time.
3. Within each candidate group, sort eligible posts by timestamp and scan rolling windows of configurable duration. Use a proposed default of 60 minutes; a rolling window can capture a burst that crosses a clock-hour boundary.
4. For each window, count posts and distinct accounts. Emit a burst candidate when at least two distinct accounts appear. Keep the minimum account count configurable for later tuning; repeated posts from one account alone do not qualify.
5. Report the window start and end, configured duration, post count, distinct account count, participating post and account IDs, plus the shared URL or text-similarity edges that connect those posts. Preserve the original related-post group even when it contains no qualifying burst.
6. Describe the result as an observed timing pattern, not an attribution of intent. Account IDs and timestamps depend on the fields exposed by each platform; display-name-based actor IDs may not uniquely identify accounts.
