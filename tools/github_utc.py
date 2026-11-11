#!/usr/bin/env python3
"""Get a fresh GitHub HTTPS Date for key creation on a clock-skewed host."""
from datetime import timezone
from email.utils import parsedate_to_datetime
import subprocess
import time
import uuid


def parse_date(response):
    headers, separator, _body = response.replace('\r\n', '\n').partition('\n\n')
    lines = headers.splitlines()
    if not separator or not lines or not lines[0].startswith('HTTP/') or len(lines[0].split()) < 2 or lines[0].split()[1] != '200':
        raise ValueError('GitHub did not return an HTTP 200 response with headers')
    dates = [line.split(':', 1)[1].strip() for line in lines[1:] if line.lower().startswith('date:')]
    if len(dates) != 1:
        raise ValueError('Expected exactly one HTTPS Date header from GitHub')
    value = parsedate_to_datetime(dates[0])
    if value.tzinfo is None or value.utcoffset().total_seconds() != 0 or not 2020 <= value.year <= 2100:
        raise ValueError('Invalid GitHub UTC date')
    return int(value.astimezone(timezone.utc).timestamp())


def github_epoch():
    start = time.monotonic()
    result = subprocess.run(['gh', 'api', '--include', '--method', 'GET',
        'user?clock_probe=' + uuid.uuid4().hex,
        '--header', 'Cache-Control: no-cache'], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Could not obtain GitHub UTC. Check network/authentication; no local-clock fallback is used.')
    if time.monotonic() - start > 30:
        raise RuntimeError('GitHub time response took too long')
    return parse_date(result.stdout)


if __name__ == '__main__':
    try:
        # Allow one minute for small differences between GitHub's API and runners.
        print(github_epoch() - 60)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc))
