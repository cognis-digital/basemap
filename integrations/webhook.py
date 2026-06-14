#!/usr/bin/env python3
"""Minimal, dependency-free webhook forwarder for Cognis findings.

Reads JSON findings on stdin and POSTs them to a URL (SIEM/Slack/Jira bridge).
Usage:  <tool> scan . --format json | python integrations/webhook.py --url URL
"""
from __future__ import annotations

import argparse
import sys
import urllib.request

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Post JSON findings from stdin to a webhook URL."
    )
    ap.add_argument("--url", required=True, help="Destination URL for the POST request")
    ap.add_argument("--header", action="append", default=[], help="Extra header in 'Key: Value' form")
    args = ap.parse_args()

    if not args.url.startswith(("http://", "https://")):
        print(f"error: --url must start with http:// or https://, got: {args.url!r}", file=sys.stderr)
        return 1

    try:
        payload = sys.stdin.buffer.read()
    except OSError as exc:
        print(f"error: failed to read stdin: {exc}", file=sys.stderr)
        return 1

    if not payload:
        print("error: no input received on stdin", file=sys.stderr)
        return 1

    req = urllib.request.Request(args.url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    for h in args.header:
        k, _, v = h.partition(":")
        key = k.strip()
        value = v.strip()
        if not key:
            print(f"error: malformed header (missing key): {h!r}", file=sys.stderr)
            return 1
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print(f"posted {len(payload)} bytes -> {r.status}")
        return 0
    except Exception as exc:
        print(f"webhook error: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
