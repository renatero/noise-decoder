// Requires Node 22.15+; optional install: npm install @bsky/jetstream
// Current SDK documented at https://bsky.network/docs/jetstream-sdk/
// Run with a time limit; this is a live stream, not a one-shot query.
import { Jetstream } from '@bsky/jetstream';

const client = new Jetstream('https://jetstream.us-east.bsky.network');
const keyword = (process.argv[2] || 'climate').toLowerCase();

for await (const event of client.live({ collections: ['app.bsky.feed.post'] })) {
  // Account and sync events can invalidate retained state too.
  if (event.kind !== 'commit') {
    if (event.kind === 'account' || event.kind === 'sync') {
      console.log(JSON.stringify(event));
    }
    continue;
  }
  const commit = event.commit;
  // Forward deletes and updates even without a keyword match: an edit might
  // remove a previously matching keyword. Reconcile these in the downstream
  // store; checkpoint the sequence only after committing the change.
  if (commit.operation === 'delete' || commit.operation === 'update' ||
      (commit.record?.text || '').toLowerCase().includes(keyword)) {
    console.log(JSON.stringify(event));
  }
}
