#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
既存の YouTube Music プレイリストを取得して、
ytm_playlist.py と同じ形の results.json を書き出す。

こちらのモードでは songs.txt を使わない。曲目リストはプレイリストの
実物から作るので、ページの表示と実際の中身がずれることが起きない。

認証は不要(公開/限定公開なら取得できる)。

    python fetch_playlist.py --config page.json --out-dir out
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List

MUSIC = "https://music.youtube.com"


def to_results(playlist: Dict, playlist_id: str) -> Dict:
    """get_playlist の戻り値を results.json の形に変換する。"""
    found: List[Dict] = []
    for t in playlist.get("tracks") or []:
        vid = t.get("videoId")
        if not vid:
            continue                      # 削除済み・非公開の曲は飛ばす
        album = t.get("album")
        album_name = album.get("name", "") if isinstance(album, dict) else (album or "")
        artists = ", ".join(a.get("name", "") for a in (t.get("artists") or [])
                            if a.get("name"))
        found.append({
            "query_title": t.get("title") or "",
            "query_artists": [],
            "title": t.get("title") or "",
            "artists": artists,
            "videoId": vid,
            "album": album_name,
            "duration": t.get("duration") or "",
            "needs_review": False,
            "reasons": [],
        })

    return {
        "source": "playlist",
        "playlist_id": playlist_id,
        "playlist_title": playlist.get("title") or "",
        "found": found,
        "missing": [],
        "urls": [f"{MUSIC}/playlist?list={playlist_id}"],
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="既存プレイリストから results.json を作る")
    p.add_argument("--config", default="page.json")
    p.add_argument("--out-dir", default="out")
    args = p.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    playlist_id = str(cfg.get("playlist_id") or "").strip()
    if not playlist_id:
        print("エラー: playlist_id が設定されていません。", file=sys.stderr)
        return 1

    print(f"プレイリストを取得します: {playlist_id}")
    try:
        from ytmusicapi import YTMusic
        pl = YTMusic().get_playlist(playlist_id, limit=None)
    except Exception as exc:                       # noqa: BLE001
        print(f"エラー: 取得できませんでした: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("       ID が正しいか、非公開になっていないか確認してください。", file=sys.stderr)
        return 1

    data = to_results(pl, playlist_id)
    if not data["found"]:
        print("エラー: 曲が 1 件も取得できませんでした。", file=sys.stderr)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, "results.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"  タイトル: {data['playlist_title']}")
    print(f"  曲数: {len(data['found'])}")
    print(f"保存しました: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
