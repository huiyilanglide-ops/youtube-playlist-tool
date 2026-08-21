#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Music に本物のプレイリストを作成 / 更新する。

認証が必要(検索と違い、書き込みのため)。次の環境変数を使う。
    YTM_CLIENT_ID      Google Cloud の OAuth クライアント ID
    YTM_CLIENT_SECRET  同シークレット
    YTM_OAUTH_JSON     ytm_auth.py が出力したトークン JSON

page.json に playlist_id があれば中身をその曲順に合わせ、
無ければ新規作成して playlist_id を書き戻す。

    python sync_playlist.py --results out/results.json --config page.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, Sequence, Tuple


def plan_changes(current: Sequence[str], target: Sequence[str]) -> Tuple[List[str], List[str]]:
    """既存プレイリストを target に近づけるための (追加, 削除) を返す。

    プレイリスト ID を変えると共有リンクが切れるため、作り直さず差分で合わせる。
    """
    current_set = list(dict.fromkeys(current))
    target_set = list(dict.fromkeys(target))
    to_add = [v for v in target_set if v not in current_set]
    to_remove = [v for v in current_set if v not in target_set]
    return to_add, to_remove


def build_client():
    client_id = os.environ.get("YTM_CLIENT_ID", "").strip()
    client_secret = os.environ.get("YTM_CLIENT_SECRET", "").strip()
    oauth_json = os.environ.get("YTM_OAUTH_JSON", "").strip()

    missing = [n for n, v in (("YTM_CLIENT_ID", client_id),
                              ("YTM_CLIENT_SECRET", client_secret),
                              ("YTM_OAUTH_JSON", oauth_json)) if not v]
    if missing:
        raise SystemExit("認証情報が足りません: " + ", ".join(missing))

    from ytmusicapi import YTMusic
    from ytmusicapi.auth.oauth import OAuthCredentials

    try:
        token = json.loads(oauth_json)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"YTM_OAUTH_JSON が JSON として読めません: {exc}") from exc

    creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
    return YTMusic(auth=token, oauth_credentials=creds)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="YouTube Music のプレイリストを作成/更新する")
    p.add_argument("--results", default="out/results.json")
    p.add_argument("--config", default="page.json")
    args = p.parse_args(argv)

    with open(args.results, encoding="utf-8") as fh:
        data = json.load(fh)
    found = data.get("found") or []
    target = [str(m["videoId"]) for m in found if m.get("videoId")]
    if not target:
        print("videoId が無いため何もしません。")
        return 0

    with open(args.config, encoding="utf-8") as fh:
        cfg: Dict = json.load(fh)

    title = cfg.get("title") or "My Playlist"
    description = cfg.get("subtitle") or ""
    privacy = (cfg.get("privacy") or "UNLISTED").upper()
    if privacy not in ("PRIVATE", "PUBLIC", "UNLISTED"):
        print(f"privacy の値が不正なので UNLISTED を使います: {privacy}")
        privacy = "UNLISTED"

    yt = build_client()
    playlist_id = str(cfg.get("playlist_id") or "").strip()

    if playlist_id:
        print(f"既存プレイリストを更新します ({len(target)} 曲)")
        try:
            existing = yt.get_playlist(playlist_id, limit=None)
        except Exception as exc:                  # noqa: BLE001
            print(f"既存プレイリストを取得できませんでした: {exc}")
            print("新規作成に切り替えます。")
            playlist_id = ""
        else:
            tracks = existing.get("tracks") or []
            current = [t.get("videoId") for t in tracks if t.get("videoId")]
            to_add, to_remove = plan_changes(current, target)

            if to_remove:
                victims = [t for t in tracks
                           if t.get("videoId") in set(to_remove) and t.get("setVideoId")]
                if victims:
                    yt.remove_playlist_items(playlist_id, victims)
                    print(f"  削除: {len(victims)} 曲")
            if to_add:
                yt.add_playlist_items(playlist_id, to_add, duplicates=False)
                print(f"  追加: {len(to_add)} 曲")
            if not to_add and not to_remove:
                print("  変更なし")

            yt.edit_playlist(playlist_id, title=title, description=description)

    if not playlist_id:
        print(f"プレイリストを新規作成します ({len(target)} 曲, {privacy})")
        created = yt.create_playlist(title, description,
                                     privacy_status=privacy, video_ids=target)
        if not isinstance(created, str):
            print(f"作成に失敗しました: {created}", file=sys.stderr)
            return 1
        playlist_id = created
        cfg["playlist_id"] = playlist_id
        with open(args.config, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        print(f"  作成しました ({len(playlist_id)} 文字) / page.json に保存しました")

    print("完了しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
