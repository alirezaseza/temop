#!/usr/bin/env python3
"""Validate / clean a subscription file BEFORE publishing it to the config repo.

Keeps only links KestrelVPN can actually run (vless/vmess/trojan/ss over tcp, ws, grpc,
httpupgrade, h2), removes duplicates, and prints a report. Fewer dead entries = faster
in-app benchmarking.

Usage: validate_subscription.py INPUT [-o OUTPUT] [--base64] [--max N]
Exit code 1 if nothing valid remains.
"""
import argparse
import base64
import json
import re
import sys
from urllib.parse import parse_qs, urlsplit, unquote

SUPPORTED_TRANSPORTS = {"", "tcp", "raw", "none", "ws", "websocket", "grpc", "httpupgrade", "h2", "http"}
SCHEMES = ("vless://", "vmess://", "trojan://", "ss://")


def b64decode(text: str):
    t = re.sub(r"\s+", "", text).rstrip("=")
    if not t or len(t) % 4 == 1:
        return None
    t = t.replace("-", "+").replace("_", "/")
    try:
        return base64.b64decode(t + "=" * (-len(t) % 4)).decode("utf-8", "replace")
    except Exception:
        return None


def check(line: str):
    """Return (key, reason). key is None when the link is rejected."""
    low = line.lower()
    try:
        if low.startswith(("vless://", "trojan://")):
            u = urlsplit(line)
            if not u.hostname or not u.port or not 1 <= u.port <= 65535 or not u.username:
                return None, "bad authority"
            q = {k.lower(): v[0] for k, v in parse_qs(u.query).items()}
            net = (q.get("type") or q.get("net") or "").lower()
            if net not in SUPPORTED_TRANSPORTS:
                return None, f"unsupported transport {net}"
            if q.get("security", "").lower() == "reality" and not q.get("pbk"):
                return None, "reality without public key"
            return (low.split("://")[0], u.hostname.lower(), u.port, unquote(u.username), net, q.get("path", ""), q.get("sni", "")), ""
        if low.startswith("vmess://"):
            raw = b64decode(line.split("://", 1)[1].split("#")[0])
            j = json.loads(raw) if raw else None
            if not isinstance(j, dict):
                return None, "bad vmess json"
            net = str(j.get("net", "")).lower()
            if net not in SUPPORTED_TRANSPORTS:
                return None, f"unsupported transport {net}"
            port = int(str(j.get("port", "0")))
            if not j.get("add") or not j.get("id") or not 1 <= port <= 65535:
                return None, "missing fields"
            return ("vmess", str(j["add"]).lower(), port, j["id"], net, j.get("path", ""), j.get("sni", "")), ""
        if low.startswith("ss://"):
            u = urlsplit(line)
            if "plugin=" in u.query.lower():
                return None, "ss plugin unsupported"
            return ("ss", line.split("#")[0]), ""
    except Exception as e:  # malformed input must never crash the pipeline
        return None, f"parse error: {e.__class__.__name__}"
    return None, "unknown scheme"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output")
    ap.add_argument("--base64", action="store_true", help="write output base64-encoded")
    ap.add_argument("--max", type=int, default=0, help="keep at most N links (0 = all)")
    a = ap.parse_args()

    text = open(a.input, encoding="utf-8", errors="replace").read().strip()
    if not any(s in text[:4096].lower() for s in SCHEMES):
        text = b64decode(text) or text

    seen, kept, reasons = set(), [], {}
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
    for line in lines:
        key, why = check(line)
        if key is None:
            reasons[why] = reasons.get(why, 0) + 1
            continue
        if key in seen:
            reasons["duplicate"] = reasons.get("duplicate", 0) + 1
            continue
        seen.add(key)
        kept.append(line)
    if a.max:
        kept = kept[: a.max]

    print(f"input lines: {len(lines)}  kept: {len(kept)}", file=sys.stderr)
    for why, n in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  dropped {n:5d}  {why}", file=sys.stderr)

    out = "\n".join(kept) + "\n"
    if a.base64:
        out = base64.b64encode(out.encode()).decode() + "\n"
    if a.output:
        open(a.output, "w", encoding="utf-8").write(out)
    else:
        sys.stdout.write(out)
    sys.exit(0 if kept else 1)


if __name__ == "__main__":
    main()
