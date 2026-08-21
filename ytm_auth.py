#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Music の書き込み用トークンを取得する(初回だけ)。

Google の「テレビ・入力が限られたデバイス」向けフローを使うので、
スマホのブラウザだけで完了できる。Colab でも動く。

    python ytm_auth.py --client-id XXX --client-secret YYY

出力された JSON を GitHub の Secret (YTM_OAUTH_JSON) に貼る。

【重要】出力は YouTube アカウントへのアクセス権そのもの。
        公開の場所(GitHub Actions のログ、Issue、SNS)に貼らないこと。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="YouTube Music のトークンを取得する")
    p.add_argument("--client-id", default=os.environ.get("YTM_CLIENT_ID", ""))
    p.add_argument("--client-secret", default=os.environ.get("YTM_CLIENT_SECRET", ""))
    p.add_argument("--attempts", type=int, default=60, help="承認待ちの試行回数")
    args = p.parse_args(argv)

    def ask(value: str, prompt: str) -> str:
        if value.strip():
            return value.strip()
        try:
            return input(prompt).strip()
        except EOFError:
            return ""

    client_id = ask(args.client_id, "OAuth クライアント ID: ")
    client_secret = ask(args.client_secret, "OAuth クライアント シークレット: ")
    if not client_id or not client_secret:
        print("クライアント ID とシークレットが必要です。", file=sys.stderr)
        print("  --client-id / --client-secret か、環境変数 "
              "YTM_CLIENT_ID / YTM_CLIENT_SECRET で渡してください。", file=sys.stderr)
        return 1

    from ytmusicapi.auth.oauth import OAuthCredentials

    creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
    code = creds.get_code()

    interval = int(code.get("interval") or 5)
    print()
    print("=" * 60)
    print("  1. 次の URL をブラウザで開く")
    print(f"       {code['verification_url']}")
    print("  2. 次のコードを入力して、Google アカウントで承認する")
    print(f"       {code['user_code']}")
    print("=" * 60)
    print()
    print("承認が終わるまでここで待ちます...")

    token = None
    for i in range(1, args.attempts + 1):
        time.sleep(interval)
        try:
            token = creds.token_from_code(code["device_code"])
        except Exception:                          # noqa: BLE001 - 未承認なら失敗する
            token = None
        if token and token.get("refresh_token"):
            break
        if i % 6 == 0:
            print(f"  まだ承認を待っています... ({i * interval} 秒経過)")

    if not token or not token.get("refresh_token"):
        print("\n時間内に承認を確認できませんでした。もう一度実行してください。", file=sys.stderr)
        return 1

    print("\n承認できました。\n")
    print("=" * 60)
    print("  次の 1 行を GitHub の Secret『YTM_OAUTH_JSON』に貼ってください")
    print("=" * 60)
    print()
    print(json.dumps(token, ensure_ascii=False, separators=(",", ":")))
    print()
    print("=" * 60)
    print("  これは YouTube アカウントへのアクセス権です。")
    print("  公開の場所には絶対に貼らないでください。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
