"""Replay ADP fixture envelopes to a running AutoDine Core HTTP endpoint."""
from __future__ import print_function

import argparse
import json
from pathlib import Path
import sys
try:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen
except ImportError:  # pragma: no cover - Python 2 compatibility not supported, keeps import explicit.
    raise


def _envelopes(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and "event_id" in value:
        return [value]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict) and "event_id" in item]
    raise ValueError("fixture must be an ADP envelope, a list, or a named envelope mapping")


def replay(path, base_url):
    with Path(path).open(encoding="utf-8") as handle:
        events = _envelopes(json.load(handle))
    endpoint = base_url.rstrip("/") + "/api/v1/events"
    for event in events:
        request = Request(
            endpoint,
            data=json.dumps(event).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            message = exc.read().decode("utf-8")
            raise RuntimeError("event {0} failed: HTTP {1}: {2}".format(event["event_id"], exc.code, message))
        if body.get("code") != 0:
            raise RuntimeError("event {0} failed: {1}".format(event["event_id"], body))
        print("{0}: {1}".format(event["event_id"], body["data"]["status"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", help="path to a JSON mock fixture")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args(argv)
    replay(args.fixture, args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
