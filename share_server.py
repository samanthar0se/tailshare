"""Static file server for sharing HTML prototypes over Tailscale.

Serves SHARE_DIR on the node's Tailscale IP so that t3code's preview pane —
which rewrites `localhost:PORT` to `<magicdns-name>:PORT` and has the *client*
fetch directly — can reach it. Binding to loopback does not work for that
reason; see the README.

Run:  python share_server.py [--port 8000] [--dir C:\\git\\.share]
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import json
import socketserver
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_PORT = 8000
DEFAULT_DIR = Path(r"C:\git\.share")
TAILSCALE_EXE = Path(r"C:\Program Files\Tailscale\tailscale.exe")

# Tailscale may not have an address yet at logon; keep retrying rather than
# dying and leaving the scheduled task in a failed state.
BIND_RETRY_SECONDS = 5
BIND_RETRY_LIMIT = 120  # ~10 minutes


def tailscale_ipv4() -> str | None:
    """Return this node's Tailscale IPv4, or None if it has no address yet."""
    if not TAILSCALE_EXE.exists():
        return None
    try:
        raw = subprocess.run(
            [str(TAILSCALE_EXE), "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    with contextlib.suppress(json.JSONDecodeError, KeyError, TypeError):
        for addr in json.loads(raw)["Self"]["TailscaleIPs"]:
            if ":" not in addr:
                return addr
    return None


def magicdns_name() -> str | None:
    """Return the node's MagicDNS name without the trailing dot."""
    if not TAILSCALE_EXE.exists():
        return None
    try:
        raw = subprocess.run(
            [str(TAILSCALE_EXE), "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    with contextlib.suppress(json.JSONDecodeError, KeyError, TypeError):
        return json.loads(raw)["Self"]["DNSName"].rstrip(".")
    return None


class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that never lets a prototype go stale.

    Prototypes are rewritten in place and re-viewed seconds later, so any
    caching at all produces confusing "I fixed that already" moments.
    """

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_head(self):  # noqa: ANN201 - matches stdlib signature
        # Defeat conditional requests entirely; If-Modified-Since on a file
        # rewritten within the same second would still yield a 304.
        if "If-Modified-Since" in self.headers:
            del self.headers["If-Modified-Since"]
        return super().send_head()

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"{self.log_date_time_string()} {fmt % args}\n")
        sys.stderr.flush()


class ReusableServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def wait_for_bind_address() -> str:
    for attempt in range(BIND_RETRY_LIMIT):
        ip = tailscale_ipv4()
        if ip:
            return ip
        if attempt == 0:
            print("waiting for a Tailscale IPv4 address...", file=sys.stderr, flush=True)
        time.sleep(BIND_RETRY_SECONDS)
    raise SystemExit("no Tailscale IPv4 address after 10 minutes; giving up")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="append stdout/stderr here; required when run windowless via pythonw.exe",
    )
    args = parser.parse_args()

    if args.log is not None:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        stream = args.log.open("a", encoding="utf-8", buffering=1)
        sys.stdout = stream
        sys.stderr = stream

    args.dir.mkdir(parents=True, exist_ok=True)

    bind_ip = wait_for_bind_address()
    handler = functools.partial(NoCacheHandler, directory=str(args.dir))

    try:
        server = ReusableServer((bind_ip, args.port), handler)
    except OSError as exc:
        raise SystemExit(f"cannot bind {bind_ip}:{args.port} - {exc}") from exc

    host = magicdns_name() or bind_ip
    print(f"serving {args.dir}", file=sys.stderr)
    print(f"  http://{host}:{args.port}/", file=sys.stderr)
    print(f"  http://{bind_ip}:{args.port}/", file=sys.stderr, flush=True)

    with server:
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()


if __name__ == "__main__":
    main()
