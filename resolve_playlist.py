#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch_videos の URL からプレイリスト ID を解決する。

watch_videos は一時プレイリストを作ってリダイレクトするため、
リダイレクト後の URL に list=... が含まれる。これを拾えば
music.youtube.com のリンクが作れる(= YouTube Music アプリで開ける)。

取れなくても致命的ではないので、失敗しても終了コード 0 で返し、
呼び出し側はセットアップ案内にフォールバックする。

    python resolve_playlist.py --results out/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# 一時プレイリストは TLGG..., 通常のプレイリストは PL... / OLAK5uy... など
ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")


def extract_list_id(url: str) -> str:
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    value = (qs.get("list") or [""])[0].strip()
    return value if ID_RE.match(value) else ""


def resolve(watch_url: str, timeout: float = 25.0) -> str:
    import requests

    with requests.Session() as s:
        s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        r = s.get(watch_url, allow_redirects=True, timeout=timeout)

        # 1. 最終 URL のクエリから
        found = extract_list_id(r.url)
        if found:
            return found

        # 2. 本文中の "list=..." から(リダイレクトが JS 側で行われる場合)
        m = re.search(r'[?&]list=([A-Za-z0-9_-]{10,})', r.text or "")
        if m:
            return m.group(1)

    return ""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="watch_videos からプレイリスト ID を解決する")
    p.add_argument("--results", default="out/results.json")
    args = p.parse_args(argv)

    if not os.path.exists(args.results):
        print(f"結果ファイルがありません: {args.results}", file=sys.stderr)
        return 0

    with open(args.results, encoding="utf-8") as fh:
        data = json.load(fh)

    urls = data.get("urls") or []
    if not urls:
        print("watch_videos の URL がないため解決をスキップします。")
        return 0

    try:
        playlist_id = resolve(urls[0])
    except Exception as exc:                  # noqa: BLE001 - ベストエフォート
        print(f"プレイリスト ID を解決できませんでした: {type(exc).__name__}: {exc}")
        return 0

    if not playlist_id:
        print("リダイレクト先に list= が見つかりませんでした。")
        return 0

    data["resolved_playlist_id"] = playlist_id
    with open(args.results, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)

    print(f"プレイリスト ID を解決しました ({len(playlist_id)} 文字)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
