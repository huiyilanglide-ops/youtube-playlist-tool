#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ytm_playlist.py の結果からスマートリンク用のランディングページを生成する。

リンク先はすべて music.youtube.com に統一している。
YouTube(www.youtube.com)には飛ばさない。

    python make_page.py --results out/results.json --config page.json --out site/index.html
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from string import Template
from typing import Dict, List

MUSIC = "https://music.youtube.com"

TEMPLATE = Template(r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>$title</title>
<meta name="description" content="$subtitle">
<meta property="og:title" content="$title">
<meta property="og:description" content="$subtitle">
<meta property="og:type" content="music.playlist">
<meta name="theme-color" content="#0b0b10">
<style>
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  :root {
    --accent: $accent;
    --accent2: $accent2;
    --bg: #0b0b10;
    --card: #16161f;
    --line: rgba(255,255,255,.10);
    --text: #f4f4f7;
    --muted: #a0a0b0;
  }
  html, body { margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans",
                 "Noto Sans JP", "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
    min-height: 100dvh;
    padding: env(safe-area-inset-top) 0 env(safe-area-inset-bottom);
  }
  body::before {
    content: "";
    position: fixed; inset: 0;
    background:
      radial-gradient(70% 45% at 50% 0%, color-mix(in srgb, var(--accent) 26%, transparent), transparent 70%),
      radial-gradient(60% 40% at 85% 15%, color-mix(in srgb, var(--accent2) 20%, transparent), transparent 70%);
    pointer-events: none;
    z-index: 0;
  }
  .wrap { position: relative; z-index: 1; max-width: 480px; margin: 0 auto; padding: 28px 20px 44px; }

  .art {
    width: 172px; height: 172px; margin: 0 auto 22px;
    border-radius: 22px;
    background: linear-gradient(140deg, var(--accent), var(--accent2));
    display: grid; place-items: center;
    font-size: 68px; line-height: 1;
    box-shadow: 0 18px 44px rgba(0,0,0,.55);
  }
  h1 { font-size: 26px; line-height: 1.25; margin: 0 0 6px; text-align: center; letter-spacing: -.01em; }
  .sub { margin: 0 0 4px; text-align: center; color: var(--muted); font-size: 14px; }
  .count { margin: 0 0 26px; text-align: center; color: var(--muted); font-size: 13px; }

  .notice {
    display: none;
    background: rgba(255,196,0,.11);
    border: 1px solid rgba(255,196,0,.34);
    color: #ffdf8a;
    border-radius: 14px;
    padding: 13px 15px;
    font-size: 13px;
    margin-bottom: 18px;
  }
  .notice.show { display: block; }
  .notice b { color: #fff3cd; }

  .btn {
    display: flex; align-items: center; justify-content: center; gap: 9px;
    width: 100%; padding: 17px 18px; margin-bottom: 11px;
    border: 0; border-radius: 15px;
    font-size: 16px; font-weight: 700; font-family: inherit;
    text-decoration: none; cursor: pointer;
    transition: transform .12s ease;
  }
  .btn:active { transform: scale(.977); }
  .btn.primary { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: #fff;
                 box-shadow: 0 10px 26px color-mix(in srgb, var(--accent) 34%, transparent); }
  .btn.ghost { background: var(--card); color: var(--text); border: 1px solid var(--line); }
  .btn .ico { font-size: 18px; line-height: 1; }

  .hint { margin: 2px 0 20px; text-align: center; font-size: 12px; color: var(--muted); }
  .hint a { color: var(--muted); }

  .setup {
    background: var(--card); border: 1px solid var(--line);
    border-radius: 15px; padding: 15px 17px; margin: 20px 0 0;
    font-size: 13px; color: var(--muted);
  }
  .setup b { color: var(--text); display: block; margin-bottom: 6px; font-size: 14px; }
  .setup ol { margin: 8px 0 0; padding-left: 20px; }
  .setup li { margin-bottom: 5px; }
  .setup code { background: rgba(255,255,255,.09); padding: 1px 6px; border-radius: 5px;
                font-size: 12px; word-break: break-all; }

  .tracks { list-style: none; margin: 30px 0 0; padding: 0;
            background: var(--card); border: 1px solid var(--line); border-radius: 17px; overflow: hidden; }
  .track { border-bottom: 1px solid var(--line); }
  .track:last-child { border-bottom: 0; }
  .track a { display: flex; align-items: center; gap: 14px; padding: 13px 17px;
             text-decoration: none; color: inherit; }
  .track a:active { background: rgba(255,255,255,.05); }
  .num { width: 20px; flex: none; text-align: right; color: var(--muted);
         font-size: 13px; font-variant-numeric: tabular-nums; }
  .meta { min-width: 0; flex: 1; }
  .t { display: block; font-size: 15px; font-weight: 600;
       overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .a { display: block; font-size: 12.5px; color: var(--muted);
       overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .play { flex: none; color: var(--muted); font-size: 13px; }

  footer { margin-top: 26px; text-align: center; color: var(--muted); font-size: 11.5px; line-height: 1.7; }
  footer a { color: var(--muted); }

  .toast {
    position: fixed; left: 50%; bottom: 28px; transform: translateX(-50%) translateY(14px);
    background: #fff; color: #111; font-size: 13.5px; font-weight: 600;
    padding: 11px 20px; border-radius: 999px;
    opacity: 0; pointer-events: none; transition: opacity .2s ease, transform .2s ease; z-index: 9;
  }
  .toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>
<div class="wrap">

  <div class="art">&#9835;</div>
  <h1>$title</h1>
  <p class="sub">$subtitle</p>
  <p class="count">$count曲 &middot; YouTube Music</p>

  <div class="notice" id="inapp">
    <b>アプリ内ブラウザで開いています</b><br>
    このままだと YouTube Music アプリに切り替わりません。
    右上の <b>&#8943;</b> から「ブラウザで開く」を選んでください。
  </div>

$buttons

  <p class="hint" id="hint">$hint</p>

  <button class="btn ghost" id="btnCopy" type="button">
    <span class="ico">&#128279;</span><span>リンクをコピー</span>
  </button>

  <ol class="tracks">
$tracks
  </ol>

$setup

  <footer>
    $generated<br>
    <a href="$repo">GitHub でソースを見る</a>
  </footer>
</div>

<div class="toast" id="toast">コピーしました</div>

<script>
(function () {
  "use strict";

  var YTM_PKG = "com.google.android.apps.youtube.music";

  var ua    = navigator.userAgent || "";
  var inApp = /FBAN|FBAV|FB_IAB|FBIOS|Instagram|Line\/|Twitter|KAKAOTALK|MicroMessenger|TikTok/i.test(ua);

  // Android は intent:// でアプリを名指しすると確実に開く。
  // 開けなければ browser_fallback_url でブラウザ版 YouTube Music に戻る。
  if (/Android/i.test(ua)) {
    var toIntent = function (httpsUrl) {
      return "intent://" + httpsUrl.replace(/^https:\/\//, "") +
             "#Intent;scheme=https;package=" + YTM_PKG +
             ";S.browser_fallback_url=" + encodeURIComponent(httpsUrl) + ";end";
    };
    // YouTube Music 向けのリンクだけを intent 化する。
    // 初回セットアップ用の YouTube リンクはそのまま残す。
    var links = document.querySelectorAll('a[href^="https://music.youtube.com"]');
    for (var i = 0; i < links.length; i++) {
      links[i].href = toIntent(links[i].href);
    }
  }

  if (inApp) document.getElementById("inapp").className = "notice show";

  var toast = document.getElementById("toast");
  function flash(msg) {
    toast.textContent = msg;
    toast.className = "toast show";
    setTimeout(function () { toast.className = "toast"; }, 1700);
  }

  document.getElementById("btnCopy").addEventListener("click", function () {
    var shareUrl = location.href.split("#")[0];
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(shareUrl).then(
        function () { flash("コピーしました"); },
        function () { flash(shareUrl); }
      );
    } else {
      var ta = document.createElement("textarea");
      ta.value = shareUrl;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); flash("コピーしました"); }
      catch (e) { flash(shareUrl); }
      document.body.removeChild(ta);
    }
  });
})();
</script>
</body>
</html>
""")

SETUP_BOX = """  <div class="setup">
    <b>プレイリストとして開くには（初回だけ）</b>
    YouTube Music は「その場かぎりのプレイリスト」を開けません。
    保存済みプレイリストの ID が要ります。取得は一度だけです。
    <ol>
      <li><a href="{save_url}">この保存用リンク</a>を開く（ここだけ YouTube 側です）</li>
      <li>プレイリスト名の横の「保存」をタップ</li>
      <li>保存したものを開き、URL の <code>list=</code> 以降をコピー</li>
      <li><code>page.json</code> の <code>playlist_id</code> に貼って commit</li>
    </ol>
    これで上のボタンが YouTube Music アプリを直接開くようになります。
  </div>"""


def esc(s: object) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def js_str(s: object) -> str:
    """JS の文字列リテラルに安全に埋め込む。"""
    return (str(s if s is not None else "")
            .replace("\\", "\\\\").replace('"', '\\"')
            .replace("<", "\\x3c").replace(">", "\\x3e")
            .replace("\n", "").replace("\r", ""))


def build_tracks(found: List[Dict]) -> str:
    rows = []
    for i, m in enumerate(found, 1):
        vid = str(m.get("videoId") or "")
        href = f"{MUSIC}/watch?v={esc(vid)}" if vid else "#"
        rows.append(
            '    <li class="track">'
            f'<a href="{href}">'
            f'<span class="num">{i}</span>'
            '<span class="meta">'
            f'<span class="t">{esc(m.get("title"))}</span>'
            f'<span class="a">{esc(m.get("artists"))}</span>'
            '</span>'
            '<span class="play">&#9654;</span>'
            '</a></li>'
        )
    return "\n".join(rows)


def normalize_id(value: str) -> str:
    """URL ごと貼られても list= 以降を拾う。"""
    value = str(value or "").strip()
    if "list=" in value:
        value = value.split("list=", 1)[1].split("&", 1)[0]
    return value


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="スマートリンク用のランディングページを生成する")
    p.add_argument("--results", default="out/results.json")
    p.add_argument("--config", default="page.json")
    p.add_argument("--out", default="site/index.html")
    p.add_argument("--repo", default=os.environ.get("PAGE_REPO_URL", "#"))
    args = p.parse_args(argv)

    if not os.path.exists(args.results):
        print(f"エラー: 結果ファイルがありません: {args.results}", file=sys.stderr)
        return 1

    with open(args.results, encoding="utf-8") as fh:
        data = json.load(fh)

    found = data.get("found") or []
    if not found:
        print("エラー: videoId が 1 件も無いためページを生成できません。", file=sys.stderr)
        return 1

    cfg: Dict = {}
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as fh:
            cfg = json.load(fh)

    # 優先順位: page.json の手動指定 > 自動解決した ID
    manual = normalize_id(cfg.get("playlist_id"))
    resolved = normalize_id(data.get("resolved_playlist_id"))
    playlist_id = manual or resolved

    def button(href: str, label: str, primary: bool = True) -> str:
        cls = "btn primary" if primary else "btn ghost"
        return (f'  <a class="{cls}" href="{esc(href)}">'
                f'<span class="ico">&#9654;</span><span>{esc(label)}</span></a>')

    if manual:
        # 保存済みプレイリストの ID。YouTube Music が確実に開ける唯一の形。
        music_url = f"{MUSIC}/playlist?list={playlist_id}"
        buttons = button(music_url, "YouTube Music で開く")
        setup = ""
        hint = "YouTube Music アプリが入っていればアプリで開きます。"
        mode = "固定プレイリスト"
    else:
        # 一時プレイリスト(TLGG...)も watch_videos も YouTube Music では開けず、
        # www.youtube.com に転送されてしまう。ここでは 1 曲目だけを開き、
        # プレイリスト化は保存用リンクからの初回セットアップに任せる。
        first = next((str(m.get("videoId")) for m in found if m.get("videoId")), "")
        ids = ",".join(str(m.get("videoId") or "") for m in found if m.get("videoId"))
        save_url = (f"https://www.youtube.com/playlist?list={resolved}" if resolved
                    else f"https://www.youtube.com/watch_videos?video_ids={ids}")
        buttons = "\n".join([
            button(save_url, "プレイリストを作成（初回のみ）"),
            button(f"{MUSIC}/watch?v={first}", "1曲目だけ再生する", primary=False),
        ])
        setup = SETUP_BOX.replace("{save_url}", esc(save_url))
        hint = "プレイリスト全体を共有するには、上のボタンで一度だけ作成してください。"
        mode = "要セットアップ"

    stamp = f"{len(found)} 曲 / 自動生成"

    page = TEMPLATE.substitute(
        title=esc(cfg.get("title") or "My Playlist"),
        subtitle=esc(cfg.get("subtitle") or ""),
        accent=esc(cfg.get("accent") or "#ff2d55"),
        accent2=esc(cfg.get("accent2") or "#7b5cff"),
        count=len(found),
        tracks=build_tracks(found),
        buttons=buttons,
        hint=esc(hint),
        setup=setup,
        generated=esc(stamp),
        repo=esc(args.repo),
    )

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"生成しました: {args.out} ({len(found)} 曲 / リンク: {mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
