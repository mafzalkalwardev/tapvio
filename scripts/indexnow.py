#!/usr/bin/env python3
"""Notify IndexNow search engines (Bing, Yandex, Seznam, Naver, Yep) about new or changed pages.

Runs in CI after a deploy. Only profiles whose YAML changed in this push are submitted, plus the
homepage. On the first deploy (or with --all), every URL is submitted.
Usage: python scripts/indexnow.py [--before <sha>] [--all]
"""
import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parent.parent


def changed_usernames(before: str) -> set[str] | None:
    if not before or set(before) == {"0"}:
        return None
    res = subprocess.run(["git", "diff", "--name-only", before, "HEAD", "--", "profiles/"],
                         cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    return {Path(f).stem for f in res.stdout.split() if f.endswith(".yml") and not Path(f).name.startswith("_")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yml").read_text())
    key, site = cfg.get("indexnow_key"), cfg["site_url"].rstrip("/")
    if not key:
        print("No indexnow_key in config.yml; skipping.")
        return 0
    urls = [u for u in (ROOT / "dist/urls.txt").read_text().split() if u]
    names = None if args.all else changed_usernames(args.before)
    if names is not None:
        urls = [u for u in urls if u in (site + "/", *(f"{site}/{n}/" for n in names))]
    if len(urls) <= 1 and names == set():
        print("No profile changes; nothing to submit.")
        return 0

    body = json.dumps({"host": urlparse(site).netloc, "key": key,
                       "keyLocation": f"{site}/{key}.txt", "urlList": urls[:10000]}).encode()
    req = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"IndexNow: HTTP {resp.status} for {len(urls)} URL(s)")
    except urllib.error.HTTPError as exc:  # 202 = accepted; 4xx means key not reachable yet, etc.
        print(f"IndexNow returned HTTP {exc.code}: {exc.read()[:200]!r}")
    except OSError as exc:
        print(f"IndexNow request failed: {exc}")
    for u in urls:
        print("  ", u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
