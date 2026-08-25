#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""取り込み後に page.json を「songs.txt から作り直す」状態に戻す。

既存の playlist_id を残したまま別の曲を取り込むと、そのプレイリストを
新しい曲で上書きしてしまう。事故を防ぐため取り込み時に必ず消す。

    python reset_target.py --config page.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Dict, Tuple


def reset(cfg: Dict) -> Tuple[Dict, str]:
    """playlist_id を外し、songs モードに切り替える。"""
    previous = str(cfg.get("playlist_id") or "").strip()
    new = dict(cfg)
    new["playlist_id"] = ""
    new["source"] = "songs"
    if previous:
        new["previous_playlist_id"] = previous     # 元に戻したいとき用に控える
    return new, previous


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="取り込み後の対象をリセットする")
    p.add_argument("--config", default="page.json")
    args = p.parse_args(argv)

    with open(args.config, encoding="utf-8") as fh:
        cfg = json.load(fh)

    new, previous = reset(cfg)
    with open(args.config, "w", encoding="utf-8") as fh:
        json.dump(new, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    if previous:
        print(f"既存の playlist_id を外しました（{previous} は previous_playlist_id に控えました）。")
        print("取り込んだ曲で既存プレイリストを上書きしないための措置です。")
    else:
        print("playlist_id は元から未設定でした。")
    print("source を songs に切り替えました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
