#!/usr/bin/env python3
"""
Social Media Handle Availability Checker

Checks if a username/handle is taken on major platforms by requesting
the profile URL and analyzing the HTTP response.

Usage:
    check_handles.py <handle> [--platforms PLATFORM1,PLATFORM2,...] [--json]

Examples:
    check_handles.py myproject
    check_handles.py myproject --platforms github,twitter,instagram
    check_handles.py myproject --json

Detection logic inspired by social-analyzer (github.com/qeeqbox/social-analyzer).
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Platform configs: URL template, indicators that handle does NOT exist
PLATFORMS = {
    "github": {
        "url": "https://github.com/{handle}",
        "not_found": ["This is not the web page you"],
        "found": ["profile:username"],
        "method": "content",
    },
    "twitter": {
        "url": "https://x.com/{handle}",
        "not_found": [],
        "found": [],
        "method": "status",  # 404 = available
    },
    "instagram": {
        "url": "https://www.instagram.com/{handle}/",
        "not_found": ["Sorry, this page isn't available"],
        "found": ["og:title"],
        "method": "content",
    },
    "linkedin": {
        "url": "https://www.linkedin.com/company/{handle}/",
        "not_found": ["Page not found"],
        "found": [],
        "method": "status",
    },
    "reddit_user": {
        "url": "https://www.reddit.com/user/{handle}",
        "not_found": ["Sorry, nobody"],
        "found": [],
        "method": "content",
    },
    "reddit_sub": {
        "url": "https://www.reddit.com/r/{handle}",
        "not_found": [],
        "found": [],
        "method": "status",
    },
    "youtube": {
        "url": "https://www.youtube.com/@{handle}",
        "not_found": ["This page isn't available", "404 Not Found"],
        "found": ["og:title"],
        "method": "content",
    },
    "tiktok": {
        "url": "https://www.tiktok.com/@{handle}",
        "not_found": ["Couldn't find this account"],
        "found": [],
        "method": "content",
    },
    "npm": {
        "url": "https://www.npmjs.com/~{handle}",
        "not_found": [],
        "found": [],
        "method": "status",
    },
    "pypi": {
        "url": "https://pypi.org/user/{handle}/",
        "not_found": [],
        "found": [],
        "method": "status",
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DEFAULT_PLATFORMS = ["github", "twitter", "instagram", "linkedin", "reddit_user", "youtube"]


def check_handle(handle: str, platform: str) -> dict:
    """Check handle availability on a single platform."""
    config = PLATFORMS.get(platform)
    if not config:
        return {"platform": platform, "handle": handle, "status": "unsupported", "url": ""}

    url = config["url"].format(handle=handle)
    result = {"platform": platform, "handle": handle, "url": url}

    try:
        req = Request(url, headers=HEADERS, method="GET")
        resp = urlopen(req, timeout=10)
        status_code = resp.getcode()

        if config["method"] == "status":
            # Got 200 = profile exists = taken
            result["status"] = "taken"
        else:
            # Need to check page content
            body = resp.read(50000).decode("utf-8", errors="ignore")
            # Check not-found indicators first
            for indicator in config["not_found"]:
                if indicator in body:
                    result["status"] = "available"
                    return result
            # Check found indicators
            for indicator in config["found"]:
                if indicator in body:
                    result["status"] = "taken"
                    return result
            # Got 200 with no clear signal — assume taken
            result["status"] = "taken"

    except HTTPError as e:
        if e.code == 404:
            result["status"] = "available"
        elif e.code == 403:
            result["status"] = "blocked"
        elif e.code == 429:
            result["status"] = "rate_limited"
        else:
            result["status"] = "error"
            result["error"] = str(e.code)
    except URLError:
        result["status"] = "error"
        result["error"] = "connection_failed"
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:100]

    return result


def check_handles_parallel(handle: str, platforms: list, max_workers: int = 6) -> list:
    """Check handle across multiple platforms in parallel."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_handle, handle, p): p for p in platforms
        }
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                platform = futures[future]
                results.append({
                    "platform": platform, "handle": handle,
                    "status": "error", "url": "",
                })

    # Sort by input order
    order = {p: i for i, p in enumerate(platforms)}
    results.sort(key=lambda r: order.get(r["platform"], 999))
    return results


def format_markdown(results: list) -> str:
    """Format results as a markdown table."""
    lines = ["| Platform | Handle | URL | Status |",
             "|----------|--------|-----|--------|"]

    status_display = {
        "taken": "taken",
        "available": "AVAILABLE",
        "blocked": "blocked (403)",
        "rate_limited": "rate limited",
        "error": "error",
        "unsupported": "unsupported",
    }

    for r in results:
        status = status_display.get(r["status"], r["status"])
        lines.append(f"| {r['platform']} | @{r['handle']} | {r.get('url', '')} | {status} |")

    available = [r for r in results if r["status"] == "available"]
    if available:
        lines.append("")
        lines.append("**Available handles:**")
        for r in available:
            lines.append(f"- {r['platform']}: @{r['handle']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check social media handle availability")
    parser.add_argument("handle", help="Handle/username to check")
    parser.add_argument("--platforms", default=",".join(DEFAULT_PLATFORMS),
                        help=f"Comma-separated platforms (default: {','.join(DEFAULT_PLATFORMS)})")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    parser.add_argument("--all", action="store_true", help="Check all supported platforms")

    args = parser.parse_args()

    if args.all:
        platforms = list(PLATFORMS.keys())
    else:
        platforms = [p.strip() for p in args.platforms.split(",")]

    results = check_handles_parallel(args.handle, platforms)

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
