#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
page.json のプレイリスト ID を実際に取得して検証する。

確認すること:
  - その ID のプレイリストが実在するか(ID の打ち間違い・コピー漏れの検出)
  - 中身が songs.txt から取れた曲と一致しているか

認証は不要(公開/限定公開なら取得できる)。
検証は情報提供が目的なので、失敗しても終了コード 0 を返す。

    python verify_playlist.py --results out/results.json --config page.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Sequence

MUSIC = "https://music.youtube.com"


def compare(playlist_ids: Sequence[str], target_ids: Sequence[str]) -> Dict:
    """プレイリストの中身と、こちらが期待する曲を突き合わせる。"""
    p = list(dict.fromkeys(playlist_ids))
    t = list(dict.fromkeys(target_ids))
    p_set, t_set = set(p), set(t)
    matched = [v for v in t if v in p_set]
    return {
        "matched": matched,
        "missing": [v for v in t if v not in p_set],      # 期待しているのに入っていない
        "extra": [v for v in p if v not in t_set],        # 入っているが期待していない
        "same_set": p_set == t_set,
        "same_order": p == t,
        "playlist_count": len(p),
        "target_count": len(t),
    }


def summary(lines: List[str]) -> None:
    """GitHub Actions のジョブサマリーがあれば書き出す。"""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    except OSError:
        pass


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="プレイリスト ID を実際に取得して検証する")
    p.add_argument("--results", default="out/results.json")
    p.add_argument("--config", default="page.json")
    args = p.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)
    playlist_id = str(cfg.get("playlist_id") or "").strip()

    if not playlist_id:
        print("playlist_id が未設定のため検証をスキップします。")
        return 0

    with open(args.results, encoding="utf-8") as fh:
        data = json.load(fh)
    found = data.get("found") or []
    target = [str(m["videoId"]) for m in found if m.get("videoId")]
    by_id = {str(m.get("videoId")): m for m in found}

    print(f"検証対象: {playlist_id} ({len(playlist_id)} 文字)")

    out: List[str] = ["", "## 🔍 プレイリストの検証", ""]

    try:
        from ytmusicapi import YTMusic
        yt = YTMusic()
        pl = yt.get_playlist(playlist_id, limit=None)
    except Exception as exc:                       # noqa: BLE001
        name = type(exc).__name__
        print(f"取得できませんでした: {name}: {exc}")
        out += [
            f"❌ **`{playlist_id}` を取得できませんでした**",
            "",
            f"`{name}`",
            "",
            "考えられる原因:",
            "",
            "- ID が途中で切れている（コピー漏れ）",
            "- プレイリストが**非公開**（PRIVATE）になっている",
            "- ID が間違っている",
            "",
            "プレイリスト画面の ⋯ → 共有 → リンクをコピー で取り直してください。",
        ]
        summary(out)
        return 0

    tracks = pl.get("tracks") or []
    ids = [t.get("videoId") for t in tracks if t.get("videoId")]
    title = pl.get("title") or "(タイトル不明)"
    cmp = compare(ids, target)

    print(f"  タイトル: {title}")
    print(f"  曲数: {cmp['playlist_count']} (期待 {cmp['target_count']})")
    print(f"  一致: {len(cmp['matched'])} / 不足: {len(cmp['missing'])} / 余分: {len(cmp['extra'])}")

    out += [
        f"✅ **`{playlist_id}` は実在します**",
        "",
        f"| 項目 | 値 |",
        f"|---|---|",
        f"| タイトル | {title} |",
        f"| プレイリストの曲数 | {cmp['playlist_count']} |",
        f"| ページに載せている曲数 | {cmp['target_count']} |",
        f"| 一致 | {len(cmp['matched'])} |",
        "",
    ]

    if cmp["same_set"]:
        order = "曲順も一致しています。" if cmp["same_order"] else "曲順だけ異なります（再生には支障ありません）。"
        out += [f"🎉 **中身は完全に一致しています。** {order}", ""]
    else:
        out += ["⚠️ **ページの曲目リストとプレイリストの中身が違います。**", ""]
        if cmp["missing"]:
            out += [f"ページに載っているのにプレイリストに無い曲 ({len(cmp['missing'])}):", ""]
            for v in cmp["missing"]:
                m = by_id.get(v, {})
                out.append(f"- {m.get('title', v)} / {m.get('artists', '')}")
            out.append("")
        if cmp["extra"]:
            out += [f"プレイリストにあるがページに無い曲 ({len(cmp['extra'])}):", ""]
            wanted = {t.get("videoId"): t for t in tracks}
            for v in cmp["extra"][:20]:
                t = wanted.get(v, {})
                artists = ", ".join(a.get("name", "") for a in (t.get("artists") or []) if a.get("name"))
                out.append(f"- {t.get('title', v)} / {artists}")
            if len(cmp["extra"]) > 20:
                out.append(f"- ...ほか {len(cmp['extra']) - 20} 曲")
            out.append("")
        out += ["`songs.txt` をプレイリストに合わせるか、"
                "プレイリスト側を直してください。", ""]

    summary(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
