#!/usr/bin/env python3
"""
ip_quality.py - Cross-platform IP purity check (Windows + macOS + Linux)

Lightweight rewrite of xykt/IPQuality's bash script.  Uses only the Python
standard library (no jq, dig, bc, nc dependencies required).  Calls a handful
of free public APIs and produces ANSI + JSON + Markdown reports under
reports/<label>-<timestamp>.{json,md,ansi}.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"
)
TIMEOUT = 12
RESTRICTED_COUNTRIES = {"CN", "RU", "IR", "KP", "CU", "SY", "BY", "VE"}
OPENAI_BLOCKED = {"CN", "RU", "IR", "KP", "CU", "SY", "BY", "VE", "AF", "BD"}

# ANSI helpers --------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_BLUE = "\033[34m"
_CYAN = "\033[36m"


def _enable_vt_on_windows() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


def color(text: str, code: str, enabled: bool) -> str:
    return f"{code}{text}{_RESET}" if enabled else text


# HTTP ----------------------------------------------------------------------


def _build_opener(proxy: str | None) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = []
    if proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    return urllib.request.build_opener(*handlers)


def http_get(
    url: str,
    proxy: str | None = None,
    timeout: int = TIMEOUT,
    headers: dict[str, str] | None = None,
) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with _build_opener(proxy).open(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        return 0, f"__error__: {type(e).__name__}: {e}"


def get_json(url: str, proxy: str | None = None) -> dict[str, Any] | None:
    status, body = http_get(url, proxy=proxy)
    if status != 200 or not body or body.startswith("__error__"):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


# Checks --------------------------------------------------------------------


def check_ipapi_is(ip: str | None, proxy: str | None) -> dict[str, Any]:
    q = f"?q={ip}" if ip else ""
    data = get_json(f"https://api.ipapi.is/{q}", proxy=proxy)
    if not data:
        return {"_source": "ipapi.is", "_ok": False}
    asn = data.get("asn") or {}
    company = data.get("company") or {}
    loc = data.get("location") or {}
    dc = data.get("datacenter") or {}
    return {
        "_source": "ipapi.is",
        "_ok": True,
        "ip": data.get("ip"),
        "asn": asn.get("asn"),
        "asn_org": asn.get("org") or asn.get("descr"),
        "asn_type": asn.get("type"),
        "country_code": loc.get("country_code"),
        "country": loc.get("country"),
        "city": loc.get("city"),
        "state": loc.get("state"),
        "timezone": loc.get("timezone"),
        "company_name": company.get("name"),
        "company_type": company.get("type"),
        "abuser_score": company.get("abuser_score"),
        "is_bogon": data.get("is_bogon"),
        "is_datacenter": data.get("is_datacenter"),
        "is_tor": data.get("is_tor"),
        "is_proxy": data.get("is_proxy"),
        "is_vpn": data.get("is_vpn"),
        "is_abuser": data.get("is_abuser"),
        "is_mobile": data.get("is_mobile"),
        "datacenter_name": dc.get("datacenter"),
    }


def check_ipinfo(ip: str | None, proxy: str | None) -> dict[str, Any]:
    if not ip:
        return {"_source": "ipinfo.io", "_ok": False, "_error": "ipinfo widget/demo requires an IP"}
    data = get_json(f"https://ipinfo.io/widget/demo/{ip}", proxy=proxy)
    if not data:
        return {"_source": "ipinfo.io", "_ok": False}
    payload = data.get("data") or data
    privacy = payload.get("privacy") or {}
    return {
        "_source": "ipinfo.io",
        "_ok": True,
        "ip": payload.get("ip"),
        "country_code": payload.get("country"),
        "country": payload.get("country_name") or payload.get("country"),
        "city": payload.get("city"),
        "region": payload.get("region"),
        "org": payload.get("org") or (payload.get("asn") or {}).get("name"),
        "asn": (payload.get("asn") or {}).get("asn"),
        "privacy_vpn": privacy.get("vpn"),
        "privacy_proxy": privacy.get("proxy"),
        "privacy_tor": privacy.get("tor"),
        "privacy_relay": privacy.get("relay"),
        "privacy_hosting": privacy.get("hosting"),
    }


def check_ip_api_com(ip: str | None, proxy: str | None) -> dict[str, Any]:
    target = ip or ""
    url = f"http://ip-api.com/json/{target}?fields=66846719"
    data = get_json(url, proxy=proxy)
    if not data or data.get("status") != "success":
        return {"_source": "ip-api.com", "_ok": False}
    return {
        "_source": "ip-api.com",
        "_ok": True,
        "ip": data.get("query"),
        "country_code": data.get("countryCode"),
        "country": data.get("country"),
        "city": data.get("city"),
        "region": data.get("regionName"),
        "isp": data.get("isp"),
        "org": data.get("org"),
        "asn": data.get("as"),
        "mobile": data.get("mobile"),
        "proxy": data.get("proxy"),
        "hosting": data.get("hosting"),
    }


def check_cloudflare_trace(proxy: str | None) -> dict[str, Any]:
    status, body = http_get("https://www.cloudflare.com/cdn-cgi/trace", proxy=proxy)
    if status != 200:
        return {"_source": "cloudflare-trace", "_ok": False}
    out = {"_source": "cloudflare-trace", "_ok": True}
    for line in body.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def check_chatgpt(proxy: str | None) -> dict[str, Any]:
    """Probe ChatGPT availability via its Cloudflare trace + a HEAD on chatgpt.com."""
    out: dict[str, Any] = {"_source": "chatgpt", "_ok": True}
    status, body = http_get("https://chat.openai.com/cdn-cgi/trace", proxy=proxy)
    out["trace_status"] = status
    loc = None
    if status == 200:
        for line in body.splitlines():
            if line.startswith("loc="):
                loc = line.split("=", 1)[1]
                break
    out["loc"] = loc

    status2, body2 = http_get("https://chatgpt.com/", proxy=proxy)
    out["chatgpt_status"] = status2
    blocked_marker = "unsupported_country" in (body2 or "").lower()
    loc_upper = (loc or "").upper()
    if blocked_marker or loc_upper in OPENAI_BLOCKED:
        out["unlocked"] = False
        out["reason"] = "blocked_page" if blocked_marker else f"loc={loc}"
    elif loc_upper and loc_upper not in OPENAI_BLOCKED:
        # loc resolved and not in blocked set -> region permits ChatGPT,
        # even if HTTP status is 403 (Cloudflare anti-bot for unauth requests).
        out["unlocked"] = True
        out["reason"] = f"loc={loc} (region permits; http={status2})"
    else:
        out["unlocked"] = None
        out["reason"] = f"loc={loc}, http={status2}"
    return out


# Aggregation ---------------------------------------------------------------


def aggregate(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ipapi = results.get("ipapi.is") or {}
    ipinfo = results.get("ipinfo.io") or {}
    ipapi_com = results.get("ip-api.com") or {}
    chatgpt = results.get("chatgpt") or {}
    cf = results.get("cloudflare-trace") or {}

    ip = ipapi.get("ip") or cf.get("ip") or ipinfo.get("ip") or ipapi_com.get("ip")
    cc = (ipapi.get("country_code") or ipinfo.get("country_code") or ipapi_com.get("country_code") or "").upper()

    flags = {
        "vpn": any([ipapi.get("is_vpn"), ipinfo.get("privacy_vpn")]),
        "proxy": any([ipapi.get("is_proxy"), ipinfo.get("privacy_proxy"), ipapi_com.get("proxy")]),
        "tor": any([ipapi.get("is_tor"), ipinfo.get("privacy_tor")]),
        "relay": bool(ipinfo.get("privacy_relay")),
        "hosting_or_dc": any([
            ipapi.get("is_datacenter"),
            ipinfo.get("privacy_hosting"),
            ipapi_com.get("hosting"),
            (ipapi.get("company_type") or "").lower() == "hosting",
            (ipapi.get("asn_type") or "").lower() == "hosting",
        ]),
        "abuser": bool(ipapi.get("is_abuser")),
        "mobile": any([ipapi.get("is_mobile"), ipapi_com.get("mobile")]),
    }

    abuse_score = ipapi.get("abuser_score")
    abuse_score_num: float | None = None
    if abuse_score is not None:
        # ipapi.is returns formats like 0.0012 or "0.0012 (Low)" or "0.32 (Medium)"
        try:
            abuse_score_num = float(abuse_score)
        except (TypeError, ValueError):
            import re

            m = re.search(r"-?\d+(?:\.\d+)?", str(abuse_score))
            if m:
                try:
                    abuse_score_num = float(m.group(0))
                except ValueError:
                    abuse_score_num = None

    verdict = "good"
    reasons: list[str] = []
    if cc in RESTRICTED_COUNTRIES:
        verdict = "bad"
        reasons.append(f"country={cc} (restricted)")
    if chatgpt.get("unlocked") is False:
        verdict = "bad"
        reasons.append(f"ChatGPT blocked ({chatgpt.get('reason')})")
    if flags["abuser"]:
        verdict = "bad"
        reasons.append("flagged as abuser")
    if abuse_score_num is not None and abuse_score_num >= 0.75:
        verdict = "bad"
        reasons.append(f"abuse score high ({abuse_score_num})")

    if verdict != "bad":
        if flags["vpn"] or flags["proxy"] or flags["tor"]:
            verdict = "warn"
            reasons.append("identified as VPN/Proxy/Tor by at least one source")
        if flags["hosting_or_dc"]:
            verdict = "warn"
            reasons.append("hosting/datacenter ASN")
        if abuse_score_num is not None and abuse_score_num >= 0.25:
            verdict = "warn"
            reasons.append(f"moderate abuse score ({abuse_score_num})")
        if chatgpt.get("unlocked") is None and verdict == "good":
            reasons.append("ChatGPT status unknown (network or rate-limited)")

    return {
        "ip": ip,
        "country_code": cc,
        "country": ipapi.get("country") or ipinfo.get("country") or ipapi_com.get("country"),
        "city": ipapi.get("city") or ipinfo.get("city") or ipapi_com.get("city"),
        "asn": ipapi.get("asn") or ipinfo.get("asn") or ipapi_com.get("asn"),
        "asn_org": ipapi.get("asn_org") or ipinfo.get("org") or ipapi_com.get("isp") or ipapi_com.get("org"),
        "company_type": ipapi.get("company_type"),
        "asn_type": ipapi.get("asn_type"),
        "abuse_score": abuse_score_num,
        "flags": flags,
        "chatgpt_unlocked": chatgpt.get("unlocked"),
        "chatgpt_reason": chatgpt.get("reason"),
        "verdict": verdict,
        "reasons": reasons,
    }


# Rendering -----------------------------------------------------------------


def render_console(summary: dict[str, Any], details: dict[str, dict[str, Any]], use_color: bool) -> str:
    lines: list[str] = []

    def c(text: str, code: str) -> str:
        return color(text, code, use_color)

    verdict = summary["verdict"]
    badge = {
        "good": c(" GOOD ", _GREEN + _BOLD),
        "warn": c(" WARN ", _YELLOW + _BOLD),
        "bad": c(" BAD  ", _RED + _BOLD),
    }.get(verdict, verdict)

    lines.append("")
    lines.append(c("=" * 64, _DIM))
    lines.append(f" IP Quality Report   verdict: {badge}")
    lines.append(c("=" * 64, _DIM))
    lines.append(f"  IP        : {c(summary['ip'] or '?', _BOLD)}")
    lines.append(
        f"  Location  : {summary.get('country') or '?'} ({summary.get('country_code') or '?'})"
        f"  - {summary.get('city') or '?'}"
    )
    lines.append(f"  ASN       : AS{summary.get('asn') or '?'}  {summary.get('asn_org') or ''}")
    lines.append(
        f"  Type      : asn={summary.get('asn_type') or '?'}  company={summary.get('company_type') or '?'}"
    )
    lines.append(f"  Abuse sc. : {summary.get('abuse_score')}")
    flags = summary["flags"]

    def flag(name: str) -> str:
        v = flags.get(name)
        marker = "yes" if v else "no"
        col = _RED if v else _GREEN
        return f"{name}={c(marker, col)}"

    lines.append(
        "  Flags     : "
        + "  ".join(flag(k) for k in ("vpn", "proxy", "tor", "relay", "hosting_or_dc", "abuser", "mobile"))
    )
    chatgpt = summary.get("chatgpt_unlocked")
    chatgpt_str = {True: c("UNLOCKED", _GREEN), False: c("BLOCKED", _RED), None: c("UNKNOWN", _YELLOW)}.get(chatgpt, "?")
    lines.append(f"  ChatGPT   : {chatgpt_str}  ({summary.get('chatgpt_reason')})")
    if summary["reasons"]:
        lines.append(c("  Reasons   :", _BOLD))
        for r in summary["reasons"]:
            lines.append(f"    - {r}")

    lines.append("")
    lines.append(c("--- per-source ---", _DIM))
    for name, src in details.items():
        ok = src.get("_ok")
        tag = c("OK", _GREEN) if ok else c("FAIL", _RED)
        lines.append(f"  [{tag}] {name}")
        if not ok:
            continue
        short_keys = [
            "ip", "country_code", "country", "city", "asn", "asn_org", "asn_type",
            "company_type", "abuser_score", "is_vpn", "is_proxy", "is_tor",
            "is_datacenter", "is_abuser", "is_mobile",
            "privacy_vpn", "privacy_proxy", "privacy_tor", "privacy_hosting", "privacy_relay",
            "proxy", "hosting", "mobile", "isp", "org",
            "loc", "trace_status", "chatgpt_status", "unlocked", "reason",
        ]
        for k in short_keys:
            if k in src and src[k] not in (None, ""):
                lines.append(f"        {k:>16} : {src[k]}")
    lines.append("")
    return "\n".join(lines)


def render_markdown(summary: dict[str, Any], details: dict[str, dict[str, Any]], label: str, ts: str) -> str:
    flags = summary["flags"]
    md = [
        f"# IP Quality Report - {label} - {ts}",
        "",
        f"- **Verdict**: `{summary['verdict']}`",
        f"- **IP**: `{summary.get('ip')}`",
        f"- **Country**: {summary.get('country')} (`{summary.get('country_code')}`) - {summary.get('city')}",
        f"- **ASN**: AS{summary.get('asn')} {summary.get('asn_org')}",
        f"- **Type**: asn=`{summary.get('asn_type')}` company=`{summary.get('company_type')}`",
        f"- **Abuse score (ipapi.is)**: {summary.get('abuse_score')}",
        f"- **ChatGPT**: unlocked=`{summary.get('chatgpt_unlocked')}` ({summary.get('chatgpt_reason')})",
        "",
        "## Flags",
        "",
        "| flag | value |",
        "|---|---|",
    ]
    for k in ("vpn", "proxy", "tor", "relay", "hosting_or_dc", "abuser", "mobile"):
        md.append(f"| {k} | {flags.get(k)} |")
    md.append("")
    if summary["reasons"]:
        md.append("## Reasons")
        md.append("")
        for r in summary["reasons"]:
            md.append(f"- {r}")
        md.append("")
    md.append("## Per-source detail")
    md.append("")
    md.append("```json")
    md.append(json.dumps(details, indent=2, ensure_ascii=False))
    md.append("```")
    return "\n".join(md)


# Entry ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-platform IP purity check")
    parser.add_argument("--ip", help="Target IP (default: this machine's egress)")
    parser.add_argument("--proxy", help="HTTP(S) proxy URL, e.g. http://127.0.0.1:6174")
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent.parent / "reports"),
        help="Where to write reports (default: <repo>/reports)",
    )
    parser.add_argument("--label", default="local", help="Report label, e.g. local or jp-01")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color in console + .ansi file")
    parser.add_argument("--json-only", action="store_true", help="Only write JSON file; suppress console output")
    args = parser.parse_args()

    _enable_vt_on_windows()
    use_color = not args.no_color

    details: dict[str, dict[str, Any]] = {}
    start = time.time()
    if not args.json_only:
        print(color("Resolving egress IP via cloudflare-trace ...", _DIM, use_color))

    # Step 1 - resolve egress IP first (most other lookups want a concrete IP).
    cf = check_cloudflare_trace(args.proxy)
    details["cloudflare-trace"] = cf
    resolved_ip = args.ip or cf.get("ip")

    if not args.json_only:
        if resolved_ip:
            print(color(f"  egress IP = {resolved_ip}", _DIM, use_color))
        else:
            print(color("  WARNING: could not resolve egress IP, some sources may fail", _YELLOW, use_color))
        print(color("Running 4 sources in parallel ...", _DIM, use_color))

    # Step 2 - parallel lookups, all keyed to resolved_ip.
    checks = {
        "ipapi.is": lambda: check_ipapi_is(resolved_ip, args.proxy),
        "ipinfo.io": lambda: check_ipinfo(resolved_ip, args.proxy),
        "ip-api.com": lambda: check_ip_api_com(resolved_ip, args.proxy),
        "chatgpt": lambda: check_chatgpt(args.proxy),
    }
    with ThreadPoolExecutor(max_workers=len(checks)) as pool:
        futures = {pool.submit(fn): name for name, fn in checks.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                details[name] = fut.result()
            except Exception as e:
                details[name] = {"_source": name, "_ok": False, "_error": str(e)}

    elapsed = time.time() - start
    summary = aggregate(details)
    summary["elapsed_seconds"] = round(elapsed, 2)

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"{args.label}-{ts}"

    full = {"summary": summary, "details": details, "args": {"ip": args.ip, "proxy": args.proxy, "label": args.label}}
    base.with_suffix(".json").write_text(json.dumps(full, indent=2, ensure_ascii=False), encoding="utf-8")

    console_text = render_console(summary, details, use_color)
    base.with_suffix(".ansi").write_text(console_text, encoding="utf-8")

    md_text = render_markdown(summary, details, args.label, ts)
    base.with_suffix(".md").write_text(md_text, encoding="utf-8")

    if not args.json_only:
        print(console_text)
        print(f"Reports written to: {base}.{{json,ansi,md}}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
