"""Small, read-only API examples; Python 3.10+, standard library only.

Run: python3 integration_examples.py --query climate --limit 3
Optional: --source bluesky --source gdelt (access/throttling may prevent results).
One page per source, no background service, storage, article fetching or deployment.
This demonstrates normalization, NOT complete collection or redistribution permission.
"""
import argparse
from datetime import datetime, timezone
import json
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MAX_BYTES = 2_000_000


def get_json(url, params):
    request = Request(url + '?' + urlencode(params), headers={
        'User-Agent': 'NoiseDecoder-ResearchExample/1.0',
        'Accept': 'application/json',
    })
    with urlopen(request, timeout=25) as response:
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Response exceeds example body limit')
        return json.loads(body)


def normalize(source, identifier, url, title, published_at=None, observed_at=None):
    return {
        'id': f'{source}:{identifier}',
        'source': source,
        'source_id': str(identifier),
        'url': url,
        'title': title,
        'published_at': published_at,
        'observed_at': observed_at,
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'rights_status': 'source-specific; not cleared for unrestricted redistribution',
    }


def fetch(source, query, limit):
    if source == 'hn':
        data = get_json('https://hn.algolia.com/api/v1/search_by_date', {
            'query': query, 'tags': 'story', 'hitsPerPage': limit, 'page': 0,
        })
        return [normalize('hn', x['objectID'],
                          'https://news.ycombinator.com/item?id=' + x['objectID'],
                          x.get('title'), x.get('created_at')) for x in data['hits']]
    if source == 'federal-register':
        data = get_json('https://www.federalregister.gov/api/v1/documents.json', {
            'conditions[term]': query, 'per_page': limit, 'order': 'newest',
        })
        return [normalize(source, x['document_number'], x.get('html_url'),
                          x.get('title'), x.get('publication_date')) for x in data['results']]
    if source == 'gdelt':
        data = get_json('https://api.gdeltproject.org/api/v2/doc/doc', {
            'query': query, 'mode': 'artlist', 'format': 'json',
            'maxrecords': limit, 'timespan': '24h',
        })
        # seendate is observation time; do not present it as publisher publication time.
        return [normalize(source, x['url'], x['url'], x.get('title'),
                          observed_at=x.get('seendate')) for x in data.get('articles', [])]
    if source == 'bluesky':
        data = get_json('https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts', {
            'q': query, 'limit': limit, 'sort': 'latest',
        })
        records = []
        for x in data.get('posts', []):
            did = x['author']['did']
            record_key = x['uri'].rsplit('/', 1)[-1]
            records.append(normalize(source, x['uri'],
                                     f'https://bsky.app/profile/{did}/post/{record_key}',
                                     x['record'].get('text'), x['record'].get('createdAt'),
                                     x.get('indexedAt')))
        return records
    raise ValueError('Unsupported source')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', default='climate')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--source', action='append', choices=['hn','federal-register','gdelt','bluesky'])
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error('--limit must be between 1 and 20')
    failed = False
    for source in dict.fromkeys(args.source or ['hn', 'federal-register']):
        try:
            records = fetch(source, args.query, args.limit)
            for record in records:
                print(json.dumps(record, ensure_ascii=False))
            print(json.dumps({'source': source, 'status': 'ok', 'records': len(records),
                              'coverage': 'one page only'}), file=sys.stderr)
        except HTTPError as exc:
            failed = True
            print(json.dumps({'source': source, 'status': exc.code,
                              'retry_after': exc.headers.get('Retry-After'),
                              'action': 'Stop; review access or retry later under provider limits'}),
                  file=sys.stderr)
        except (OSError, ValueError, KeyError) as exc:
            failed = True
            print(json.dumps({'source': source, 'status': 'error', 'detail': str(exc)}), file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
