"""Private operator configuration. Secrets never appear in API responses."""
from contextlib import closing
from pathlib import Path
import hmac
import json
import os
import re
import secrets
import sqlite3
import time

PROVIDERS = {
    'openrouter': {'name': 'OpenRouter · Jev', 'env': 'OPENROUTER_API_KEY', 'enabled': False, 'model': '~typesafe/jev-latest', 'base_url': 'https://openrouter.ai/api'},
    'context': {'name': 'Context.dev', 'env': 'CONTEXT_API_KEY', 'enabled': True, 'model': '', 'base_url': 'https://api.context.dev/v1'},
    'cala': {'name': 'Cala.ai', 'env': 'CALA_API_KEY', 'enabled': False, 'model': '', 'base_url': 'https://api.cala.ai/v1'},
    'featherless': {'name': 'Featherless', 'env': 'FEATHERLESS_API_KEY', 'enabled': False, 'model': 'Qwen/Qwen2.5-7B-Instruct', 'base_url': 'https://api.featherless.ai/v1'},
    'verda': {'name': 'Verda (NVIDIA models only)', 'env': 'VERDA_API_KEY', 'enabled': False, 'model': '', 'base_url': 'https://inference.verda.com/v1'},
}

VERDA_CONTAINER_BASE = r'https://containers\.(?:verda\.com|datacrunch\.io)/[a-zA-Z0-9_-]+/v1'


def state_dir():
    path = Path(os.environ.get('NOISE_STATE_DIR', '.noise-state'))
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def initialize():
    path = state_dir() / 'operator-token'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return path
    with os.fdopen(fd, 'w') as stream:
        stream.write(secrets.token_urlsafe(36) + '\n')
    return path


def authorized(token):
    expected = initialize().read_text().strip()
    return bool(token) and hmac.compare_digest(token.encode(), expected.encode())


def database():
    path = state_dir() / 'providers.sqlite3'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    os.close(fd)
    path.chmod(0o600)
    db = sqlite3.connect(path, timeout=10)
    db.execute('CREATE TABLE IF NOT EXISTS config (provider TEXT PRIMARY KEY, value TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS calls (provider TEXT, created REAL)')
    db.commit()
    return db


def get_config(provider):
    defaults = PROVIDERS[provider]
    result = {**defaults, 'api_key': os.environ.get(defaults['env'], '').strip()}
    with closing(database()) as db:
        row = db.execute('SELECT value FROM config WHERE provider=?', (provider,)).fetchone()
    if row:
        result.update(json.loads(row[0]))
    return result


def api_key(provider):
    config = get_config(provider)
    return config['api_key'] if config['enabled'] else ''


def public_config(provider):
    config = get_config(provider)
    return {key: config[key] for key in ('name', 'enabled', 'model', 'base_url')} | {
        'id': provider, 'key_configured': bool(config['api_key']),
    }


def save_config(provider, patch):
    # Merge under a write transaction so simultaneous edits do not lose fields.
    if provider not in PROVIDERS:
        raise ValueError('Unknown provider.')
    values = {k: v for k, v in patch.items() if k in ('api_key', 'enabled', 'model', 'base_url') and v is not None}
    if values.get('api_key') == '':
        del values['api_key']  # blank fields preserve the existing credential
    if patch.get('remove_key'):
        values['api_key'] = ''  # explicitly overrides any environment key too
    if 'api_key' in values and (len(values['api_key']) > 512 or any(c.isspace() for c in values['api_key'])):
        raise ValueError('API keys must contain no whitespace and at most 512 characters.')
    if provider == 'openrouter' and 'model' in values:
        if values['model'] == 'jev-latest':
            values['model'] = '~typesafe/jev-latest'
        if not re.fullmatch(r'(?:~typesafe/jev-latest|typesafe/jev-[A-Za-z0-9.-]+)', values['model']):
            raise ValueError('Use ~typesafe/jev-latest or an exact typesafe/jev- model ID.')
    elif 'model' in values and not re.fullmatch(r'[A-Za-z0-9_./:-]{0,200}', values['model']):
        raise ValueError('Invalid model ID.')
    if 'base_url' in values:
        base = values['base_url'].rstrip('/')
        if provider == 'verda':
            if base != PROVIDERS['verda']['base_url'] and not re.fullmatch(VERDA_CONTAINER_BASE, base):
                raise ValueError('Use the Verda managed endpoint or https://containers.verda.com/DEPLOYMENT/v1 (containers.datacrunch.io is also supported).')
        elif base != PROVIDERS[provider]['base_url']:
            raise ValueError('This provider uses its fixed official API endpoint.')
        values['base_url'] = base
    with closing(database()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM config WHERE provider=?', (provider,)).fetchone()
        current = json.loads(row[0]) if row else {}
        current.update(values)
        db.execute('INSERT OR REPLACE INTO config VALUES (?,?)', (provider, json.dumps(current)))
    return public_config(provider)


def reserve_call(provider):
    """Durable per-provider cap: 4/minute, 20/day; failures also consume a slot."""
    now = time.time()
    with closing(database()) as db, db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM calls WHERE created < ?', (now - 31 * 86400,))
        minute, day, month = [db.execute('SELECT COUNT(*) FROM calls WHERE provider=? AND created>=?', (provider, since)).fetchone()[0]
                              for since in (now - 60, int(now // 86400) * 86400, now - 30 * 86400)]
        if minute >= 4 or day >= 20 or (provider == 'cala' and month >= 90):
            raise ValueError('Application request budget reached: 4/minute, 20/day, and 90/30 days for Cala. Failed requests also count.')
        db.execute('INSERT INTO calls VALUES (?,?)', (provider, now))


if __name__ == '__main__':
    print('Operator token stored at:', initialize().resolve())
