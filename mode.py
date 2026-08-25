#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""page.json を見て、曲目リストの供給元を判定する。

    playlist : 既存プレイリストの中身をそのまま使う
    songs    : songs.txt を検索して組み立てる
"""
import json
import sys


def detect(cfg: dict) -> str:
    src = str(cfg.get("source") or "").strip().lower()
    if src in ("playlist", "songs"):
        return src
    return "playlist" if str(cfg.get("playlist_id") or "").strip() else "songs"


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "page.json"
    with open(path, encoding="utf-8") as fh:
        print(detect(json.load(fh)))
