#!/usr/bin/env python3
"""
Domain Availability Checker

Checks domain name availability across multiple TLDs using a cascade:
  1. DNS lookup (fast, stdlib) — if resolves, domain is taken
  2. WHOIS verification (accurate) — confirms availability via python-whois or system whois

Usage:
    check_domains.py <name> [<name>...] [--tlds TLD1,TLD2,...] [--json] [--whois]

Examples:
    check_domains.py myapp coolproject
    check_domains.py myapp --tlds com,io,dev,ai
    check_domains.py myapp --whois --json
"""

import argparse
import json
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

DEFAULT_TLDS = ["com", "io", "dev", "ai", "co", "app", "net", "org", "me", "sh"]

# Minimum domain name length per TLD (registry rules)
TLD_MIN_LENGTH = {
    "com": 2, "net": 2, "org": 2, "io": 2, "ai": 2,
    "co": 3, "me": 3, "app": 3, "dev": 3, "sh": 2,
}


def is_valid_domain_name(name: str, tld: str) -> bool:
    """Validate domain name against registry rules."""
    min_len = TLD_MIN_LENGTH.get(tld, 3)
    if len(name) < min_len or len(name) > 63:
        return False
    if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', name):
        return False
    if '--' in name:
        return False
    return True


def check_dns(domain: str, timeout: float = 5.0) -> bool:
    """Check if a domain resolves via DNS. Returns True if it resolves (likely taken)."""
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo(domain, 80)
        return True
    except (socket.gaierror, socket.timeout, OSError):
        return False
    finally:
        socket.setdefaulttimeout(old_timeout)


def check_whois(domain: str) -> Optional[bool]:
    """
    Check domain via WHOIS. Returns:
    - True if registered (taken)
    - False if available
    - None if check failed
    """
    # Try python-whois library first
    try:
        import whois
        w = whois.whois(domain)
        if w is None:
            return False
        if hasattr(w, 'status'):
            if w.status is None or (isinstance(w.status, list) and len(w.status) == 0):
                return False
        if hasattr(w, 'domain_name') and w.domain_name is None:
            return False
        return True
    except ImportError:
        pass
    except Exception:
        pass

    # Fall back to system whois command
    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.lower()
        not_found = [
            "no match", "not found", "no entries found", "no data found",
            "available", "status: free", "no object found",
        ]
        for indicator in not_found:
            if indicator in output:
                return False
        if output.strip():
            return True
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def check_domain(name: str, tld: str, use_whois: bool = False) -> dict:
    """Check availability of a single domain name + TLD combination."""
    domain = f"{name}.{tld}"
    result = {"domain": domain, "name": name, "tld": tld}

    if not is_valid_domain_name(name, tld):
        result["status"] = "invalid"
        result["method"] = "validation"
        return result

    # Step 1: Fast DNS check
    dns_resolves = check_dns(domain)

    if dns_resolves:
        result["status"] = "taken"
        result["method"] = "dns"
        return result

    # Step 2: WHOIS verification (if requested)
    if use_whois:
        whois_result = check_whois(domain)
        if whois_result is True:
            result["status"] = "taken"
            result["method"] = "whois"
        elif whois_result is False:
            result["status"] = "available"
            result["method"] = "whois"
        else:
            result["status"] = "unknown"
            result["method"] = "whois_failed"
    else:
        result["status"] = "possibly_available"
        result["method"] = "dns"

    return result


def check_domains_parallel(names: list, tlds: list, use_whois: bool = False, max_workers: int = 10) -> list:
    """Check multiple domains in parallel using thread pool."""
    all_results = []
    tasks = [(n.lower().strip(), t) for n in names for t in tlds]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_domain, name, tld, use_whois): (name, tld)
            for name, tld in tasks
        }
        for future in as_completed(futures):
            try:
                all_results.append(future.result())
            except Exception:
                name, tld = futures[future]
                all_results.append({
                    "domain": f"{name}.{tld}", "name": name, "tld": tld,
                    "status": "error", "method": "exception",
                })

    # Sort by input order
    order = {f"{n}.{t}": i for i, (n, t) in enumerate(tasks)}
    all_results.sort(key=lambda r: order.get(r["domain"], 999))
    return all_results


def format_markdown(results: list) -> str:
    """Format results as a markdown table."""
    lines = ["| Domain | Status | Method |", "|--------|--------|--------|"]

    status_display = {
        "taken": "taken",
        "available": "AVAILABLE",
        "possibly_available": "possibly available",
        "unknown": "unknown",
        "invalid": "invalid name",
        "error": "error",
    }

    for r in results:
        status = status_display.get(r["status"], r["status"])
        lines.append(f"| {r['domain']} | {status} | {r['method']} |")

    available = [r for r in results if r["status"] in ("available", "possibly_available")]
    if available:
        lines.append("")
        lines.append("**Potentially available domains:**")
        for r in available:
            lines.append(f"- {r['domain']}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check domain availability across TLDs")
    parser.add_argument("names", nargs="+", help="Base domain names (without TLD)")
    parser.add_argument("--tlds", default=",".join(DEFAULT_TLDS),
                        help=f"Comma-separated TLDs (default: {','.join(DEFAULT_TLDS)})")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    parser.add_argument("--whois", action="store_true", help="Use WHOIS for accuracy (slower)")

    args = parser.parse_args()
    tlds = [t.strip().lstrip(".") for t in args.tlds.split(",")]

    results = check_domains_parallel(args.names, tlds, use_whois=args.whois)

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
