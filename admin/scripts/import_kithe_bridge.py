"""Resume a local Bridge crawl through GEOMG's protected aggregate API.

Source credentials are supplied in environment; no direct database access.
Checkpoints, compressed source pages and per-batch outcomes remain outside Git.
"""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5


def request(url, *, token=None, body=None, key=None):
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Bridge-Token"] = token
    if body is not None:
        headers.update({"Content-Type": "application/json", "X-GEOMG-Request": "1", "Idempotency-Key": str(key)})
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            # Do not forward a Bridge credential through a redirect.
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None
            with urllib.request.build_opener(NoRedirect).open(req, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == 4:
                raise RuntimeError(f"HTTP {exc.code}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise RuntimeError("Connection failed after retries") from None
        print(json.dumps({'event':'retry', 'attempt':attempt+1, 'stage':'source' if token else 'local'}), flush=True)
        time.sleep(min(2 ** attempt, 16))


def atomic(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w') as output:
        json.dump(value, output)
        output.flush()
        os.fsync(output.fileno())
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--set-id', required=True)
    parser.add_argument('--api', default='http://127.0.0.1:5176')
    args = parser.parse_args()
    if urllib.parse.urlsplit(args.api).hostname not in {'127.0.0.1', 'localhost'}:
        parser.error('Only a loopback GEOMG target is allowed')
    source = os.environ['KITHE_BRIDGE_URL']
    token = os.environ['KITHE_BRIDGE_TOKEN']
    if urllib.parse.urlsplit(source).scheme != 'https':
        parser.error('Bridge source must use HTTPS')
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output/'import.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another crawler already owns this output directory')
        statefile = args.output/'checkpoint.json'
        identity = hashlib.sha256(json.dumps(['managing-set-v1', source, args.set_id]).encode()).hexdigest()
        state = json.loads(statefile.read_text()) if statefile.exists() else dict(identity=identity, page=0, cursor=None, processed=0, created=0, existing=0, invalid=0, source_deleted=0, complete=False)
        if state['identity'] != identity:
            parser.error('Checkpoint belongs to another source, Set, or legacy ownership contract; use a new output directory')
        while not state['complete']:
            number = state['page']
            sourcefile = args.output/f'page-{number:06}.json.gz'
            if sourcefile.exists():
                with gzip.open(sourcefile, 'rt') as stream:
                    page = json.load(stream)
            else:
                params = {'limit':500}
                if state['cursor']:
                    params['cursor'] = state['cursor']
                page = request(source+'?'+urllib.parse.urlencode(params), token=token)
                if not isinstance(page.get('data'), list) or (page.get('has_more') and not page.get('next_cursor')):
                    raise RuntimeError('Invalid upstream pagination')
                with gzip.open(sourcefile.with_suffix('.tmp'), 'wt') as stream:
                    json.dump(page, stream)
                sourcefile.with_suffix('.tmp').replace(sourcefile)
            if page.get('has_more') and page['next_cursor'] == state['cursor']:
                raise RuntimeError('Upstream cursor did not advance')
            records = page['data']
            page_counts = dict(created=0, existing=0, invalid=0, source_deleted=0)
            for offset in range(0, len(records), 500):
                batch = records[offset:offset+500]
                key = uuid5(NAMESPACE_URL, f'geomg-bridge:{identity}:{number}:{offset}')
                result = request(args.api+'/api/v1/admin/resources/bridge/batches', body=dict(set_id=args.set_id, records=batch), key=key)
                if len(result['items']) != len(batch):
                    raise RuntimeError('Batch outcomes did not reconcile')
                atomic(args.output/f'outcome-{number:06}-{offset}.json', result)
                for item in result['items']:
                    page_counts[item['outcome']] += 1
            state.update(page=number+1, cursor=page.get('next_cursor'), complete=not page.get('has_more'))
            state['processed'] += len(records)
            for name, count in page_counts.items():
                state[name] += count
            atomic(statefile, state)
            print(json.dumps({k:v for k,v in state.items() if k not in {'identity','cursor'}}), flush=True)



if __name__ == '__main__':
    main()
