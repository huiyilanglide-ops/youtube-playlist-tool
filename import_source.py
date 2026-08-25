#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
他サービスのプレイリストや曲名リストを取り込んで songs.txt を作る。

ここで作った songs.txt を既存の照合エンジン(ytm_playlist.py)に渡すと、
YouTube Music の楽曲(Art Track)が特定され、プレイリストとページになる。

対応している入力:
  - Spotify のプレイリスト URL   (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET が必要)
  - YouTube Music のプレイリスト URL
  - 曲名の羅列(どのサービスからコピーしても可)

    python import_source.py --source "https://open.spotify.com/playlist/xxxx"
    python import_source.py --source "Closer - The Chainsmokers
    Faded - Alan Walker"
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Dict, List, Sequence, Tuple

Track = Tuple[str, List[str]]

# 「Title - Artist」の区切りに使われがちな記号
DASHES = ("―", "—", "–", " - ", "－")
# アーティスト欄の中の区切り
ARTIST_SPLIT = re.compile(r"\s*(?:,|&|/|feat\.?|ft\.?|with|と|×|x)\s+", re.IGNORECASE)


# --------------------------------------------------------------------------
# 入力の種類を判定する
# --------------------------------------------------------------------------
def detect_kind(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return "empty"
    if "open.spotify.com" in v or v.startswith("spotify:"):
        return "spotify"
    if "music.youtube.com" in v or "youtube.com/playlist" in v:
        return "ytmusic"
    return "text"


def parse_spotify_id(value: str) -> str:
    """Spotify の URL / URI からプレイリスト ID を取り出す。"""
    m = re.search(r"playlist[/:]([A-Za-z0-9]+)", value or "")
    return m.group(1) if m else ""


def parse_ytmusic_id(value: str) -> str:
    m = re.search(r"[?&]list=([A-Za-z0-9_-]+)", value or "")
    return m.group(1) if m else ""


# --------------------------------------------------------------------------
# 曲名リストの解釈
# --------------------------------------------------------------------------
def split_artists(blob: str) -> List[str]:
    parts = [p.strip(" 　") for p in ARTIST_SPLIT.split(blob or "")]
    return [p for p in parts if p]


def parse_line(line: str, swap: bool = False) -> Track | None:
    """1 行を (曲名, アーティスト) に分解する。

    受け付ける形:
        Closer / The Chainsmokers, Halsey     <- こちらの標準形
        Closer - The Chainsmokers             <- 多くのサービスのコピー結果
        Closer — The Chainsmokers
        Closer	The Chainsmokers              <- タブ区切り
        Closer                                 <- 曲名のみ
    """
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None

    # 先頭の連番(1. / 01 / 1) など)を落とす
    line = re.sub(r"^\s*\d{1,3}\s*[.)\]。]\s+", "", line)

    title, artists_blob = line, ""
    if " / " in line:
        title, _, artists_blob = line.partition(" / ")
    elif "\t" in line:
        title, _, artists_blob = line.partition("\t")
    else:
        for d in DASHES:
            if d in line:
                title, _, artists_blob = line.partition(d)
                break

    title = title.strip(" 　")
    artists = split_artists(artists_blob)
    if swap and artists:
        # 「Artist - Title」形式だった場合
        title, artists = artists_blob.strip(" 　"), [title]
    if not title:
        return None
    return (title, artists)


def parse_text(text: str, swap: bool = False) -> List[Track]:
    out: List[Track] = []
    for raw in (text or "").splitlines():
        t = parse_line(raw, swap=swap)
        if t:
            out.append(t)
    return out


# --------------------------------------------------------------------------
# Spotify
# --------------------------------------------------------------------------
def tracks_from_spotify_items(items: Sequence[Dict]) -> List[Track]:
    """Spotify API の items[] を (曲名, アーティスト) に変換する。"""
    out: List[Track] = []
    for it in items or []:
        track = (it or {}).get("track") or {}
        name = track.get("name")
        if not name:
            continue                       # 削除済み・ローカルファイルなど
        artists = [a.get("name", "") for a in (track.get("artists") or []) if a.get("name")]
        out.append((name, artists))
    return out


def fetch_spotify(playlist_id: str, log) -> List[Track]:
    import requests

    cid = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        raise SystemExit(
            "Spotify の取り込みには認証情報が必要です。\n"
            "  SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET を設定してください。\n"
            "  https://developer.spotify.com/dashboard でアプリを作れば無料で取得できます。\n"
            "  （ユーザーのログインは不要。公開プレイリストを読むだけの権限です）")

    log("Spotify のトークンを取得します...")
    r = requests.post("https://accounts.spotify.com/api/token",
                      data={"grant_type": "client_credentials"},
                      auth=(cid, secret), timeout=20)
    if r.status_code != 200:
        raise SystemExit(f"トークンを取得できませんでした ({r.status_code}): {r.text[:200]}")
    token = r.json().get("access_token")
    if not token:
        raise SystemExit("トークンが空でした。認証情報を確認してください。")

    items: List[Dict] = []
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks?limit=100"
    while url:
        rr = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=25)
        if rr.status_code != 200:
            raise SystemExit(f"プレイリストを取得できませんでした ({rr.status_code}): "
                             f"{rr.text[:200]}\n"
                             "  公開プレイリストか確認してください。")
        data = rr.json()
        items.extend(data.get("items") or [])
        url = data.get("next")
        log(f"  {len(items)} 曲取得...")

    return tracks_from_spotify_items(items)


# --------------------------------------------------------------------------
# YouTube Music
# --------------------------------------------------------------------------
def fetch_ytmusic(playlist_id: str, log) -> List[Track]:
    from ytmusicapi import YTMusic

    log("YouTube Music のプレイリストを取得します...")
    pl = YTMusic().get_playlist(playlist_id, limit=None)
    out: List[Track] = []
    for t in pl.get("tracks") or []:
        if not t.get("title"):
            continue
        artists = [a.get("name", "") for a in (t.get("artists") or []) if a.get("name")]
        out.append((t["title"], artists))
    return out


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------
def to_songs_txt(tracks: Sequence[Track], header: str = "") -> str:
    lines = ["# import_source.py が生成しました。手で編集しても構いません。"]
    if header:
        lines.append(f"# 取り込み元: {header}")
    lines.append("")
    for title, artists in tracks:
        lines.append(f"{title} / {', '.join(artists)}" if artists else title)
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="他サービスのプレイリストから songs.txt を作る")
    p.add_argument("--source", required=True,
                   help="プレイリストの URL、または曲名の羅列")
    p.add_argument("--out", default="songs.txt")
    p.add_argument("--swap", action="store_true",
                   help="「アーティスト - 曲名」の順で書かれている場合に指定する")
    args = p.parse_args(argv)

    def log(msg: str) -> None:
        print(msg, flush=True)

    kind = detect_kind(args.source)
    log(f"入力の種類: {kind}")

    if kind == "empty":
        log("入力が空です。")
        return 1

    if kind == "spotify":
        pid = parse_spotify_id(args.source)
        if not pid:
            log("Spotify のプレイリスト ID を取り出せませんでした。")
            log("  例: https://open.spotify.com/playlist/37i9dQZF1DX...")
            return 1
        tracks = fetch_spotify(pid, log)
        header = f"Spotify playlist {pid}"
    elif kind == "ytmusic":
        pid = parse_ytmusic_id(args.source)
        if not pid:
            log("YouTube Music のプレイリスト ID を取り出せませんでした。")
            return 1
        tracks = fetch_ytmusic(pid, log)
        header = f"YouTube Music playlist {pid}"
    else:
        tracks = parse_text(args.source, swap=args.swap)
        header = "貼り付けられた曲名リスト"

    if not tracks:
        log("曲を 1 件も取り出せませんでした。")
        return 1

    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(to_songs_txt(tracks, header))

    log("")
    log(f"{len(tracks)} 曲を取り込みました:")
    for i, (title, artists) in enumerate(tracks[:30], 1):
        log(f"  {i:2}. {title} / {', '.join(artists) or '(アーティスト不明)'}")
    if len(tracks) > 30:
        log(f"  ...ほか {len(tracks) - 30} 曲")
    log("")
    log(f"保存しました: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
