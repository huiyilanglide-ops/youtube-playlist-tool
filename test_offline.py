#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ネットワーク不要のロジック検証。

ytmusicapi の返り値を模したダミーデータを流し込み、
  - MV / カラオケ / カバー / リミックス を掴まないこと
  - 正しい Art Track を選ぶこと
  - 見つからない曲を missing に振り分けること
  - watch_videos URL を正しく組み立てること
を確認する。

ここに出てくる videoId はすべてテスト用のダミー(実在しない)。

    python test_offline.py
"""
from __future__ import annotations

import sys
from typing import Dict, List

import ytm_playlist as M


def song(video_id: str, title: str, artists: List[str],
         album: str = "Test Album", duration: str = "3:45",
         result_type: str = "song") -> Dict:
    return {
        "videoId": video_id,
        "title": title,
        "artists": [{"name": a, "id": None} for a in artists],
        "album": {"name": album, "id": None} if album else None,
        "duration": duration,
        "resultType": result_type,
    }


# 検索クエリ(正規化後の部分一致)ごとに返すダミー結果
FIXTURES = {
    "closer": [
        # MV が混ざってきても resultType != song なので採用されない
        song("TESTmvAAAAA", "Closer (Official Video)", ["The Chainsmokers"],
             album="", duration="4:12", result_type="video"),
        song("TESTkarAAAAA", "Closer (Karaoke Version)", ["Sing Along Karaoke"]),
        song("TESTsongAAAA", "Closer", ["The Chainsmokers", "Halsey"], album="Collage"),
        song("TESTrmxAAAAA", "Closer (T-Mass Remix)", ["The Chainsmokers", "Halsey"]),
    ],
    "something just like this": [
        song("TESTcovBBBBB", "Something Just Like This (Cover)", ["Random Covers"]),
        song("TESTsongBBBB", "Something Just Like This",
             ["The Chainsmokers", "Coldplay"], album="Memories...Do Not Open"),
    ],
    "dont let me down": [
        song("TESTsongCCCC", "Don't Let Me Down", ["The Chainsmokers", "Daya"],
             album="Collage"),
        song("TESTliveCCCC", "Don't Let Me Down (Live)", ["The Chainsmokers"]),
    ],
    "paris": [
        # 主アーティスト一致で正しく拾えるか
        song("TESTsongDDDD", "Paris", ["The Chainsmokers"], album="Memories...Do Not Open"),
        song("TESTotheDDDD", "Paris", ["Some Other Band"], album="Unrelated"),
    ],
    "it aint me": [
        song("TESTsongEEEE", "It Ain't Me", ["Kygo", "Selena Gomez"], album="It Ain't Me"),
    ],
    "faded": [
        song("TESTsongFFFF", "Faded", ["Alan Walker"], album="Different World"),
    ],
    "7 years": [
        song("TESTsongGGGG", "7 Years", ["Lukas Graham"], album="Lukas Graham"),
    ],
    "let me love you": [
        song("TESTsongHHHH", "Let Me Love You", ["DJ Snake", "Justin Bieber"],
             album="Encore"),
        # 同名異曲(Mario)を掴まないこと
        song("TESTwrngHHHH", "Let Me Love You", ["Mario"], album="Turning Point"),
    ],
    "cold water": [
        song("TESTsongIIII", "Cold Water",
             ["Major Lazer", "Justin Bieber", "MØ"], album="Cold Water"),
    ],
    # "cheap thrills" はわざと未登録 -> 見つからない扱いになるはず
}


def fake_searcher(query: str, limit: int) -> List[Dict]:
    n_query = M.norm(query)
    for key, results in FIXTURES.items():
        if key in n_query:
            return results[:limit]
    return []


def main() -> int:
    songs = [M.Song(t, list(a)) for t, a in M.DEFAULT_SONGS]
    logs: List[str] = []
    found, missing = M.run_lookup(songs, fake_searcher, 10, logs.append)

    got = {m.song.title: m.video_id for m in found}
    expected = {
        "Closer": "TESTsongAAAA",
        "Something Just Like This": "TESTsongBBBB",
        "Don't Let Me Down": "TESTsongCCCC",
        "Paris": "TESTsongDDDD",
        "It Ain't Me": "TESTsongEEEE",
        "Faded": "TESTsongFFFF",
        "7 Years": "TESTsongGGGG",
        "Let Me Love You": "TESTsongHHHH",
        "Cold Water": "TESTsongIIII",
    }

    failures: List[str] = []
    for title, want in expected.items():
        actual = got.get(title)
        if actual != want:
            failures.append(f"  {title}: 期待 {want} / 実際 {actual}")

    missing_titles = [s.title for s in missing]
    if missing_titles != ["Cheap Thrills"]:
        failures.append(f"  missing の期待は ['Cheap Thrills'] / 実際 {missing_titles}")

    url = M.build_url([m.video_id for m in found])
    if not url.startswith(M.WATCH_VIDEOS_BASE):
        failures.append("  URL の接頭辞が不正")
    if len(url.split("video_ids=")[1].split(",")) != len(found):
        failures.append("  URL 内の ID 個数が一致しない")

    # 50 件超の分割
    chunked = M.build_urls([f"id{i:09d}" for i in range(120)])
    if len(chunked) != 3:
        failures.append(f"  120 件は 3 分割される想定 / 実際 {len(chunked)}")

    # 正規化のユニットチェック
    cases = [
        (M.norm("Don't Let Me Down"), "dont let me down"),
        (M.norm("It Ain’t Me"), "it aint me"),
        (M.norm("MØ"), "mo"),
        (M.base_title("Closer (feat. Halsey)").strip(), "Closer"),
        (M.norm(M.base_title("Faded - Official Video")), "faded"),
    ]
    for actual, want in cases:
        if actual != want:
            failures.append(f"  正規化: 期待 '{want}' / 実際 '{actual}'")

    # --- 接続エラーの扱い ---------------------------------------------
    conn_cases = [
        (RuntimeError("ProxyError: Tunnel connection failed: 403 Forbidden"), True),
        (RuntimeError("Failed to establish a new connection: [Errno -2] "
                      "Name or service not known"), True),
        (RuntimeError("HTTPSConnectionPool(host='music.youtube.com', port=443): "
                      "Read timed out."), True),
        (ValueError("Server returned unexpected JSON"), False),
        (KeyError("videoId"), False),
    ]
    for exc, want in conn_cases:
        if M._is_connection_error(exc) is not want:
            failures.append(f"  接続エラー判定: {exc!r} は {want} のはず")

    # 接続不能なら全曲を試さず即座に中断する
    def dead_searcher(query: str, limit: int):
        raise M.NetworkUnavailable("Tunnel connection failed: 403 Forbidden")

    try:
        M.run_lookup(songs, dead_searcher, 10, lambda _m: None)
        failures.append("  接続不能時に NetworkUnavailable が送出されなかった")
    except M.NetworkUnavailable:
        pass

    # 通信以外のエラーは 1 曲を諦めるだけで、処理は続行する
    def flaky_searcher(query: str, limit: int):
        raise ValueError("unexpected payload")

    try:
        f2, m2 = M.run_lookup(songs, flaky_searcher, 10, lambda _m: None)
        if f2 or len(m2) != len(songs):
            failures.append("  通信以外のエラーでは全曲 missing になるはず")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"  通信以外のエラーで中断してしまった: {exc!r}")

    print("--- 検索ログ ---")
    print("\n".join(logs))
    print()
    M.print_report(found, missing, print)
    print()

    if failures:
        print("テスト失敗:")
        print("\n".join(failures))
        return 1
    print(f"テスト成功: {len(found)} 曲一致 / missing {len(missing)} 曲 / URL 生成 OK")
    print("MV・カラオケ・カバー・リミックス・同名異曲はいずれも選ばれませんでした。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
