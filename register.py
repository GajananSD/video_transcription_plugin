"""Connect this plugin to a running Video Transcription app (from any laptop on the same network).

Usage:
    python register.py --app http://<app-laptop-ip>:8000 --team "Team B"
    python register.py --app http://<app-laptop-ip>:8000 --url http://<this-laptop-ip>:8300/insight
    python register.py --app http://<app-laptop-ip>:8000 --remove     # disconnect again

It registers the plugin via the app's REST API (POST /api/v1/extensions), then asks the app to
send a test event, which proves the app laptop can reach this laptop. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request

import config


def my_lan_ip() -> str:
    """The IP other laptops use to reach this one (no packet is actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def call(method: str, url: str, body: dict | None = None, timeout: float = 25) -> dict | list:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--app", required=True, help="Transcription app backend, e.g. http://192.168.1.20:8000")
    p.add_argument("--url", help=f"Our endpoint as the app should call it (default: http://<my-ip>:{config.PORT}/insight)")
    p.add_argument("--name", default=config.PLUGIN_NAME)
    p.add_argument("--team", default=config.TEAM_NAME, help="Your team name, shown next to the plugin in the app")
    p.add_argument("--remove", action="store_true", help="Remove plugins with this name instead")
    args = p.parse_args()

    api = args.app.rstrip("/") + "/api/v1"
    url = args.url or f"http://{my_lan_ip()}:{config.PORT}/insight"

    try:
        existing = call("GET", f"{api}/extensions")
    except (urllib.error.URLError, OSError) as exc:
        print(f"✗ Cannot reach the app at {args.app}: {exc}")
        print("  Is its backend started with --host 0.0.0.0, and is port 8000 open in its firewall?")
        return 1

    same = [e for e in existing if e["name"] == args.name]
    if args.remove:
        for e in same:
            call("DELETE", f"{api}/extensions/{e['extension_id']}")
        print(f"✓ Removed {len(same)} plugin(s) named '{args.name}'.")
        return 0

    for e in same:  # re-registering replaces the old entry (e.g. the laptop's IP changed)
        call("DELETE", f"{api}/extensions/{e['extension_id']}")
    ext = call("POST", f"{api}/extensions", {"team": args.team, "name": args.name, "url": url,
                                             "events": ["transcript.ready", "transcript.updated"]})
    print(f"✓ Registered '{ext['name']}' from {args.team or 'no team'} → {url}  (id {ext['extension_id']})")

    print("… asking the app to send us a test event")
    res = call("POST", f"{api}/extensions/{ext['extension_id']}/test")
    if res.get("ok"):
        print(f"✓ The app reached this plugin and got a valid card in {res['elapsed_ms']} ms.")
        print("  Transcribe a video in the app, then open its '🧩 Plugin results' tab.")
        return 0
    print(f"✗ The app could not use this plugin: {res.get('error')}")
    print(f"  Check that `uvicorn app:app --host 0.0.0.0 --port {config.PORT}` is running here,")
    print(f"  and that port {config.PORT} is open in this laptop's firewall (see README).")
    return 2


if __name__ == "__main__":
    sys.exit(main())
