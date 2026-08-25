#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
page.json の playlist_id を書き換える。

YouTube Music のプレイリスト URL をまるごと渡してもよい。
list= 以降を抜き出して保存する。

    python set_playlist.py --config page.json --value "https://music.youtube.com/playlist?list=PL..."
"""
from __future__ import annotations

import argparse
import json
import re
import sys

ID_RE = re.compile(r"^[A-Za-z0-9_-]{10,}$")


def extract(value: str) -> str:
    value = (value or "").strip().strip('"').strip("'")
    if not value:
        return ""
    if "list=" in value:
        value = value.split("list=", 1)[1]
    # URL の後続パラメータや余計な記号を落とす
    value = re.split(r"[&#?\s]", value, 1)[0]
    return value


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="page.json の playlist_id を設定する")
    p.add_argument("--config", default="page.json")
    p.add_argument("--value", required=True, help="プレイリストの URL または ID")
    args = p.parse_args(argv)

    playlist_id = extract(args.value)
    if not playlist_id:
        print("入力が空のため変更しません。")
        return 0

    if not ID_RE.match(playlist_id):
        raw = args.value.strip()
        looks_like_video = ("list=" not in raw) and any(
            k in raw for k in ("youtu.be/", "watch?v=", "/watch", "/shorts/"))
        print(f"エラー: プレイリスト ID として解釈できません: {raw!r}", file=sys.stderr)
        if looks_like_video:
            print("        これは動画 1 本のリンクです。プレイリストのリンクが必要です。",
                  file=sys.stderr)
            print("        再生中の画面から共有すると曲のリンクになります。",
                  file=sys.stderr)
            print("        ライブラリでプレイリストを開いてから共有してください。",
                  file=sys.stderr)
        print("        正しい形: https://music.youtube.com/playlist?list=PL...",
              file=sys.stderr)
        print("        （必ず list= が含まれます）", file=sys.stderr)
        return 1

    if playlist_id.startswith("TLGG"):
        print("エラー: これは一時プレイリスト (TLGG...) の ID です。", file=sys.stderr)
        print("        YouTube Music では開けません。先に「保存」して、", file=sys.stderr)
        print("        保存されたプレイリストの URL を使ってください。", file=sys.stderr)
        return 1

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)

    before = cfg.get("playlist_id") or ""
    cfg["playlist_id"] = playlist_id
    with open(args.config, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    action = "更新" if before else "設定"
    print(f"playlist_id を{action}しました ({len(playlist_id)} 文字)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
