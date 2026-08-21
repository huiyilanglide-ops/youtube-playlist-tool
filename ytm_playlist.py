#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Music の「楽曲(Art Track)」の videoId を取得し、
watch_videos 形式の URL を1本生成するスクリプト。

重要:
    ytmusicapi の search(filter="songs") のみを使用する。
    filter="songs" は YouTube Music の「楽曲」タブ相当であり、
    返るのは Art Track の videoId。ミュージックビデオ(MV)は
    filter="videos" 側に出るため、原理的に MV の ID は混入しない。
    さらに resultType == "song" のものだけを候補として採用する
    二重チェックを入れている。

認証: 不要(検索のみ)。

使い方:
    python ytm_playlist.py
    python ytm_playlist.py --songs songs.txt
    python ytm_playlist.py --limit 15 --out-dir out
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------
# 曲リスト(デフォルト)
#   タイトルとアーティストを分けて持つことで、検索結果の照合精度を上げる。
# --------------------------------------------------------------------------
DEFAULT_SONGS: List[Tuple[str, List[str]]] = [
    ("Closer",                   ["The Chainsmokers", "Halsey"]),
    ("Something Just Like This", ["The Chainsmokers", "Coldplay"]),
    ("Don't Let Me Down",        ["The Chainsmokers", "Daya"]),
    ("Paris",                    ["The Chainsmokers"]),
    ("It Ain't Me",              ["Kygo", "Selena Gomez"]),
    ("Faded",                    ["Alan Walker"]),
    ("7 Years",                  ["Lukas Graham"]),
    ("Let Me Love You",          ["DJ Snake", "Justin Bieber"]),
    ("Cold Water",               ["Major Lazer", "Justin Bieber"]),
    ("Cheap Thrills",            ["Sia"]),
]

WATCH_VIDEOS_BASE = "https://www.youtube.com/watch_videos?video_ids="
WATCH_VIDEOS_MAX = 50  # watch_videos が一度に受け付ける ID 数の上限

# --------------------------------------------------------------------------
# 文字列正規化
# --------------------------------------------------------------------------
_TRANS = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "–": "-", "—": "-",
    "ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ß": "ss",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "á": "a", "à": "a", "â": "a", "ä": "a", "å": "a",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ñ": "n", "ç": "c",
})


def norm(s: Optional[str]) -> str:
    """比較用に文字列を正規化する。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.translate(_TRANS)
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"['`’]", "", s)          # don't -> dont
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def base_title(s: Optional[str]) -> str:
    """(feat. X) / [Official Video] などの付随表記を落とした主タイトル。"""
    if not s:
        return ""
    s = re.sub(r"[\(\[\{][^\)\]\}]*[\)\]\}]", " ", str(s))
    s = re.sub(r"\s+(feat|ft|featuring|with)\.?\s+.*$", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*[-–—]\s*(official|lyric|audio|video|mv)\b.*$", " ", s, flags=re.IGNORECASE)
    return s.strip()


def _contains_phrase(haystack: str, needle: str) -> bool:
    """単語境界つきの部分一致(正規化済み文字列を想定)。"""
    if not needle or not haystack:
        return False
    return re.search(r"(?:^| )" + re.escape(needle) + r"(?: |$)", haystack) is not None


# --------------------------------------------------------------------------
# 「これは狙った音源ではない」ことを示すマーカー
# --------------------------------------------------------------------------
HARD_BAD = (
    "karaoke", "tribute", "made famous by", "in the style of", "originally performed",
    "nightcore", "8d", "lofi", "lo fi", "instrumental", "cover", "backing track",
    "workout mix", "ringtone",
)
SOFT_BAD = (
    "remix", "live", "acoustic", "sped up", "slowed", "reverb", "mashup",
    "bootleg", "extended", "demo", "reprise", "re recorded", "rerecorded",
    "tiktok", "edit",
)


# --------------------------------------------------------------------------
# データ構造
# --------------------------------------------------------------------------
@dataclass
class Song:
    title: str
    artists: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        a = ", ".join(self.artists) if self.artists else "(アーティスト指定なし)"
        return f"{self.title} / {a}"


@dataclass
class Match:
    song: Song
    video_id: str
    title: str
    artists: str
    album: str
    duration: str
    score: float
    title_score: float
    matched_artists: List[str]
    needs_review: bool
    reasons: List[str]


# --------------------------------------------------------------------------
# スコアリング
# --------------------------------------------------------------------------
def score_candidate(song: Song, item: Dict) -> Optional[Dict]:
    """検索結果 1 件を採点する。楽曲として不適格なら None。"""
    video_id = item.get("videoId")
    if not video_id:
        return None

    # filter="songs" でも念のため resultType を確認する(MV 混入の二重防止)。
    result_type = (item.get("resultType") or "").lower()
    if result_type and result_type != "song":
        return None

    r_title = item.get("title") or ""
    r_artists = [a.get("name", "") for a in (item.get("artists") or []) if a.get("name")]
    album_obj = item.get("album")
    r_album = (album_obj or {}).get("name", "") if isinstance(album_obj, dict) else (album_obj or "")

    n_rtitle_full = norm(r_title)
    n_rtitle = norm(base_title(r_title))
    n_qtitle = norm(base_title(song.title))
    n_query = norm(f"{song.title} {' '.join(song.artists)}")
    n_rart = norm(" , ".join(r_artists))

    # --- タイトル一致度 ---
    if n_rtitle and n_rtitle == n_qtitle:
        t_score = 100.0
    elif n_qtitle and n_rtitle.startswith(n_qtitle + " "):
        t_score = 82.0
    elif _contains_phrase(n_rtitle, n_qtitle):
        t_score = 66.0
    else:
        q_tokens = set(n_qtitle.split())
        r_tokens = set(n_rtitle.split())
        t_score = 50.0 * len(q_tokens & r_tokens) / len(q_tokens) if q_tokens else 0.0

    # --- アーティスト一致度 ---
    matched: List[str] = []
    if song.artists:
        for a in song.artists:
            na = norm(a)
            cands = {na}
            cands.add(na[4:] if na.startswith("the ") else "the " + na)
            if any(_contains_phrase(n_rart, c) for c in cands if c):
                matched.append(a)
        a_score = 100.0 * len(matched) / len(song.artists)
        if matched and matched[0] == song.artists[0]:
            a_score += 25.0            # 主アーティスト一致のボーナス
    else:
        a_score = 60.0                 # 指定なしのときは中立値

    # --- ペナルティ ---
    penalty = 0.0
    reasons: List[str] = []
    haystack = f"{n_rtitle_full} {n_rart}"
    for bad in HARD_BAD:
        if _contains_phrase(haystack, bad) and not _contains_phrase(n_query, bad):
            penalty += 150.0
            reasons.append(f"除外語:{bad}")
    for bad in SOFT_BAD:
        if _contains_phrase(haystack, bad) and not _contains_phrase(n_query, bad):
            penalty += 40.0
            reasons.append(f"別バージョンの可能性:{bad}")

    bonus = 30.0 if result_type == "song" else 0.0   # 楽曲であることの加点
    bonus += 10.0 if r_album else 0.0                # Art Track はアルバムを持つ

    total = 3.0 * t_score + 2.0 * a_score + bonus - penalty

    return {
        "videoId": video_id,
        "title": r_title,
        "artists": ", ".join(r_artists),
        "album": r_album,
        "duration": item.get("duration") or "",
        "score": total,
        "title_score": t_score,
        "matched_artists": matched,
        "reasons": reasons,
    }


def is_acceptable(song: Song, cand: Dict) -> bool:
    """採用してよい水準かどうか。"""
    if cand["title_score"] < 66.0:
        return False
    if song.artists and not cand["matched_artists"]:
        return False
    return True


def needs_review(song: Song, cand: Dict) -> Tuple[bool, List[str]]:
    """採用はするが目視確認を促すべきか。"""
    reasons = list(cand["reasons"])
    if cand["title_score"] < 100.0:
        reasons.append("タイトル完全一致ではない")
    if song.artists and len(cand["matched_artists"]) < len(song.artists):
        missing = [a for a in song.artists if a not in cand["matched_artists"]]
        reasons.append("未一致アーティスト: " + ", ".join(missing))
    return (len(reasons) > 0, reasons)


# --------------------------------------------------------------------------
# 検索
# --------------------------------------------------------------------------
def query_variants(song: Song) -> List[str]:
    """ヒット率を上げるための検索クエリ候補(順に試す)。"""
    variants: List[str] = []
    if song.artists:
        variants.append(f"{song.title} {' '.join(song.artists)}")
        variants.append(f"{song.title} {song.artists[0]}")
    variants.append(song.title)
    seen, out = set(), []
    for v in variants:
        key = norm(v)
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out


class NetworkUnavailable(RuntimeError):
    """YouTube Music に到達できない(接続/プロキシ/DNS の問題)。"""


_CONN_MARKERS = (
    "proxyerror", "connectionerror", "connecttimeout", "readtimeout",
    "newconnectionerror", "maxretryerror", "sslerror", "timeout",
    "timed out", "name or service not known", "temporary failure in name resolution",
    "failed to establish a new connection", "tunnel connection failed",
    "connection refused", "network is unreachable",
)


def _is_connection_error(exc: BaseException) -> bool:
    """通信そのものが成立していないタイプの例外か。"""
    blob = f"{type(exc).__name__} {exc}".lower()
    return any(m in blob for m in _CONN_MARKERS)


def _brief(exc: BaseException, limit: int = 160) -> str:
    """ログ用に例外メッセージを短くする。"""
    msg = " ".join(str(exc).split())
    if len(msg) > limit:
        msg = msg[:limit] + "..."
    return f"{type(exc).__name__}: {msg}"


Searcher = Callable[[str, int], List[Dict]]


def _make_session(timeout: float):
    """全リクエストに既定のタイムアウトを付けた requests セッション。"""
    import requests

    class _TimeoutSession(requests.Session):
        def request(self, *args, **kwargs):        # type: ignore[override]
            kwargs.setdefault("timeout", timeout)
            return super().request(*args, **kwargs)

    return _TimeoutSession()


def make_ytmusic_searcher(log: Callable[[str], None], attempts: int = 3,
                          timeout: float = 20.0) -> Searcher:
    """ytmusicapi を使う検索関数を返す(一時的な通信エラーはリトライ)。"""
    from ytmusicapi import YTMusic

    yt = _retry(lambda: YTMusic(requests_session=_make_session(timeout)),
                log, attempts, "YTMusic の初期化")

    def _search(query: str, limit: int) -> List[Dict]:
        # ここが要:filter="songs" 固定。MV(filter="videos")は取得しない。
        return _retry(lambda: yt.search(query, filter="songs", limit=limit),
                      log, attempts, f"検索 '{query}'")

    return _search


def _retry(fn, log: Callable[[str], None], attempts: int, what: str):
    delay = 2.0
    last: Optional[Exception] = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:              # noqa: BLE001 - 通信系は何が来るか読めない
            last = exc
            if i == attempts:
                break
            log(f"    ! {what} に失敗 ({_brief(exc)})"
                f" — {delay:.0f} 秒後に再試行 [{i}/{attempts - 1}]")
            time.sleep(delay)
            delay *= 2

    # 接続自体が張れない場合は、全曲を延々と試しても無駄なので専用の例外にする。
    if last is not None and _is_connection_error(last):
        raise NetworkUnavailable(f"{what}: {_brief(last, 300)}") from last
    raise RuntimeError(f"{what} が {attempts} 回失敗しました: {_brief(last, 300)}") from last


def lookup_song(song: Song, searcher: Searcher, limit: int,
                log: Callable[[str], None]) -> Optional[Match]:
    """1 曲ぶんの videoId を決定する。"""
    best: Optional[Dict] = None
    for query in query_variants(song):
        try:
            results = searcher(query, limit)
        except NetworkUnavailable:
            raise                              # 環境の問題。上位で中断する。
        except Exception as exc:              # noqa: BLE001
            log(f"    ! 検索エラー: {_brief(exc)}")
            continue

        for item in results or []:
            cand = score_candidate(song, item)
            if cand and (best is None or cand["score"] > best["score"]):
                best = cand

        # 文句なしの一致が取れたら以降のクエリは省略する
        if best and best["title_score"] >= 100.0 and not best["reasons"] \
                and (not song.artists or len(best["matched_artists"]) == len(song.artists)):
            break

    if not best or not is_acceptable(song, best):
        return None

    review, reasons = needs_review(song, best)
    return Match(
        song=song,
        video_id=best["videoId"],
        title=best["title"],
        artists=best["artists"],
        album=best["album"],
        duration=best["duration"],
        score=best["score"],
        title_score=best["title_score"],
        matched_artists=best["matched_artists"],
        needs_review=review,
        reasons=reasons,
    )


def run_lookup(songs: Sequence[Song], searcher: Searcher, limit: int,
               log: Callable[[str], None]) -> Tuple[List[Match], List[Song]]:
    found: List[Match] = []
    missing: List[Song] = []
    total = len(songs)
    for i, song in enumerate(songs, 1):
        log(f"[{i}/{total}] 検索中: {song.label}")
        match = lookup_song(song, searcher, limit, log)
        if match:
            flag = "  ※要確認" if match.needs_review else ""
            log(f"    -> {match.video_id}  ({match.title} / {match.artists}){flag}")
            found.append(match)
        else:
            log("    -> 見つかりませんでした")
            missing.append(song)
    return found, missing


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------
def build_url(video_ids: Sequence[str]) -> str:
    return WATCH_VIDEOS_BASE + ",".join(video_ids)


def build_urls(video_ids: Sequence[str]) -> List[str]:
    """50 件を超える場合は分割して複数の URL を返す。"""
    return [build_url(video_ids[i:i + WATCH_VIDEOS_MAX])
            for i in range(0, len(video_ids), WATCH_VIDEOS_MAX)] or []


def print_report(found: List[Match], missing: List[Song], out: Callable[[str], None]) -> None:
    out("")
    out("=" * 72)
    out(f"取得できた曲 ({len(found)} 曲)   形式: 曲名 / アーティスト / videoId")
    out("=" * 72)
    for i, m in enumerate(found, 1):
        mark = " ※要確認" if m.needs_review else ""
        out(f"{i:2}. {m.title} / {m.artists} / {m.video_id}{mark}")
        extra = []
        if m.album:
            extra.append(f"アルバム: {m.album}")
        if m.duration:
            extra.append(f"長さ: {m.duration}")
        if extra:
            out(f"    {'  '.join(extra)}")
        if m.needs_review:
            out(f"    確認理由: {'; '.join(m.reasons)}")

    out("")
    out("=" * 72)
    out(f"見つからなかった曲 ({len(missing)} 曲)")
    out("=" * 72)
    if missing:
        for i, s in enumerate(missing, 1):
            out(f"{i:2}. {s.label}")
    else:
        out("なし — 全曲取得できました。")

    out("")
    out("=" * 72)
    out("プレイリスト URL (watch_videos 形式)")
    out("=" * 72)
    if found:
        urls = build_urls([m.video_id for m in found])
        for u in urls:
            out(u)
        if len(urls) > 1:
            out("")
            out(f"※ videoId が {WATCH_VIDEOS_MAX} 件を超えたため URL を分割しました。")
    else:
        out("videoId が 1 件も取得できなかったため URL を生成できませんでした。")


def save_outputs(found: List[Match], missing: List[Song], out_dir: str,
                 log: Callable[[str], None]) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # CSV は Excel でそのまま開けるよう BOM 付き UTF-8 にする
    csv_path = os.path.join(out_dir, "results.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["#", "検索した曲名", "検索したアーティスト", "取得した曲名",
                    "取得したアーティスト", "videoId", "アルバム", "長さ",
                    "要確認", "備考"])
        for i, m in enumerate(found, 1):
            w.writerow([i, m.song.title, ", ".join(m.song.artists), m.title,
                        m.artists, m.video_id, m.album, m.duration,
                        "はい" if m.needs_review else "いいえ", "; ".join(m.reasons)])
        for s in missing:
            w.writerow(["", s.title, ", ".join(s.artists), "", "", "", "", "",
                        "", "見つかりませんでした"])

    url_path = os.path.join(out_dir, "playlist_url.txt")
    with open(url_path, "w", encoding="utf-8") as fh:
        for u in build_urls([m.video_id for m in found]):
            fh.write(u + "\n")

    json_path = os.path.join(out_dir, "results.json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump({
            "found": [{
                "query_title": m.song.title,
                "query_artists": m.song.artists,
                "title": m.title,
                "artists": m.artists,
                "videoId": m.video_id,
                "album": m.album,
                "duration": m.duration,
                "needs_review": m.needs_review,
                "reasons": m.reasons,
            } for m in found],
            "missing": [{"title": s.title, "artists": s.artists} for s in missing],
            "urls": build_urls([m.video_id for m in found]),
        }, fh, ensure_ascii=False, indent=2)

    log("")
    log(f"保存しました: {csv_path}")
    log(f"保存しました: {url_path}")
    log(f"保存しました: {json_path}")


# --------------------------------------------------------------------------
# 入力
# --------------------------------------------------------------------------
def load_songs(path: Optional[str]) -> List[Song]:
    """曲リストを読み込む。

    songs.txt の書式(1 行 1 曲):
        Closer / The Chainsmokers, Halsey     <- 推奨。照合精度が上がる
        Cheap Thrills                          <- タイトルのみでも可
        # で始まる行と空行は無視
    """
    if not path:
        return [Song(t, list(a)) for t, a in DEFAULT_SONGS]

    songs: List[Song] = []
    with open(path, "r", encoding="utf-8-sig") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "/" in line:
                title, _, artists = line.partition("/")
                songs.append(Song(title.strip(),
                                  [a.strip() for a in artists.split(",") if a.strip()]))
            else:
                songs.append(Song(line, []))
    if not songs:
        raise SystemExit(f"曲リストが空です: {path}")
    return songs


def _setup_stdout() -> None:
    """Windows のコンソール(cp932)で UnicodeEncodeError にならないようにする。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    _setup_stdout()

    p = argparse.ArgumentParser(
        description="YouTube Music の楽曲(Art Track)の videoId を集めて watch_videos URL を作る")
    p.add_argument("--songs", help="曲リストのファイル (未指定ならスクリプト内蔵のリスト)")
    p.add_argument("--limit", type=int, default=10, help="1 クエリあたりの検索件数 (既定: 10)")
    p.add_argument("--out-dir", default="out", help="結果の保存先 (既定: out)")
    p.add_argument("--no-files", action="store_true", help="ファイルを保存しない")
    p.add_argument("--timeout", type=float, default=20.0,
                   help="1 リクエストのタイムアウト秒 (既定: 20)")
    args = p.parse_args(argv)

    songs = load_songs(args.songs)

    def log(msg: str) -> None:
        print(msg, flush=True)

    log(f"対象: {len(songs)} 曲")
    log("方式: ytmusicapi search(filter=\"songs\") — 楽曲(Art Track)のみ。MV は取得しません。")
    log("")

    def network_error(exc: BaseException) -> int:
        log("")
        log("=" * 72)
        log("エラー: YouTube Music に接続できませんでした。")
        log("=" * 72)
        log(f"詳細: {exc}")
        log("")
        log("確認してください:")
        log("  - インターネットに接続されているか")
        log("  - 会社/学校のネットワークやファイアウォールが")
        log("    music.youtube.com を遮断していないか")
        log("  - プロキシ環境なら HTTPS_PROXY 環境変数が正しいか")
        log("  - VPN やセキュリティソフトが通信を止めていないか")
        log("")
        log("videoId が 1 件も取得できていないため、URL は生成していません。")
        return 1

    try:
        searcher = make_ytmusic_searcher(log, timeout=args.timeout)
    except ImportError:
        log("エラー: ytmusicapi が見つかりません。次を実行してください:")
        log("    pip install ytmusicapi")
        return 1
    except NetworkUnavailable as exc:
        return network_error(exc)
    except Exception as exc:                  # noqa: BLE001
        return network_error(exc)

    try:
        found, missing = run_lookup(songs, searcher, args.limit, log)
    except NetworkUnavailable as exc:
        # 接続が張れない状態で全曲を試しても無駄なので、ここで打ち切る。
        return network_error(exc)

    print_report(found, missing, log)

    if not args.no_files:
        try:
            save_outputs(found, missing, args.out_dir, log)
        except OSError as exc:
            log(f"警告: ファイルを保存できませんでした: {exc}")

    return 0 if found else 2


if __name__ == "__main__":
    raise SystemExit(main())
