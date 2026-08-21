#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytm_playlist.py の結果 (out/results.json) を
スマホでも読みやすい Markdown にして標準出力へ書き出す。

GitHub Actions のジョブサマリー用:
    python to_summary.py >> "$GITHUB_STEP_SUMMARY"
"""
from __future__ import annotations

import json
import os
import sys

RESULTS = os.environ.get("RESULTS_JSON", "out/results.json")
LOG = os.environ.get("RUN_LOG", "run.log")


def out(line: str = "") -> None:
    print(line)


def emit_failure() -> None:
    out("## ❌ 取得に失敗しました")
    out()
    out("`videoId` が 1 件も取得できなかったため、URL は生成していません。")
    out()
    if os.path.exists(LOG):
        try:
            with open(LOG, encoding="utf-8", errors="replace") as fh:
                tail = fh.read().splitlines()[-40:]
        except OSError:
            tail = []
        if tail:
            out("<details><summary>実行ログ(末尾40行)</summary>")
            out()
            out("```")
            for line in tail:
                out(line)
            out("```")
            out()
            out("</details>")
            out()
    out("YouTube Music 側がこのランナーからの検索を弾いた可能性があります。")
    out("しばらく待って再実行するか、README の Colab / Windows の手順をお試しください。")


def main() -> int:
    if not os.path.exists(RESULTS):
        emit_failure()
        return 0

    try:
        with open(RESULTS, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        out("## ❌ 結果ファイルを読めませんでした")
        out()
        out(f"`{RESULTS}`: {exc}")
        return 0

    found = data.get("found") or []
    missing = data.get("missing") or []
    urls = data.get("urls") or []

    if not found or not urls:
        emit_failure()
        return 0

    out("## 🎵 プレイリスト URL")
    out()
    for i, url in enumerate(urls, 1):
        label = "▶ タップして再生" if len(urls) == 1 else f"▶ タップして再生 ({i}/{len(urls)})"
        out(f"### [{label}]({url})")
        out()
        out("コピー用:")
        out()
        out("```text")
        out(url)
        out("```")
        out()

    out("> 初回に開くと一時的なプレイリストが作られます。")
    out("> 残したい場合は再生画面の「保存」でライブラリに入れてください。")
    out("> ライブラリは YouTube と YouTube Music で共有されます。")
    out()

    out(f"## ✅ 取得できた曲 ({len(found)} / {len(found) + len(missing)})")
    out()
    out("| # | 曲名 | アーティスト | videoId |")
    out("|---:|---|---|---|")
    for i, m in enumerate(found, 1):
        mark = " ⚠️" if m.get("needs_review") else ""
        title = str(m.get("title", "")).replace("|", "\\|")
        artists = str(m.get("artists", "")).replace("|", "\\|")
        out(f"| {i} | {title}{mark} | {artists} | `{m.get('videoId','')}` |")
    out()

    review = [m for m in found if m.get("needs_review")]
    if review:
        out("<details><summary>⚠️ 要確認の曲とその理由</summary>")
        out()
        for m in review:
            out(f"- **{m.get('title','')}** / {m.get('artists','')} "
                f"(アルバム: {m.get('album') or '不明'})")
            for r in m.get("reasons") or []:
                out(f"  - {r}")
        out()
        out("</details>")
        out()

    out(f"## ⚠️ 見つからなかった曲 ({len(missing)})")
    out()
    if missing:
        for m in missing:
            artists = ", ".join(m.get("artists") or []) or "(指定なし)"
            out(f"- {m.get('title','')} / {artists}")
        out()
        out("`songs.txt` を編集して曲名やアーティスト表記を変えると見つかることがあります。")
    else:
        out("なし — 全曲取得できました。")
    out()

    out("---")
    out()
    out("曲を変えたいときは `songs.txt` を編集して commit すると、")
    out("このワークフローが自動で再実行されます。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
