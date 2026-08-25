#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全モジュールのオフライン検証。ネットワーク不要。

    python test_all.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import List

import fetch_playlist
import import_source as I
import reset_target
import make_page
import mode
import resolve_playlist
import set_playlist
import sync_playlist
import verify_playlist
import ytm_playlist as M
import test_offline as T

FAILS: List[str] = []


def check(cond: bool, label: str) -> None:
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def section(name: str) -> None:
    print(f"\n--- {name} ---")


def make_results(tmp: str) -> str:
    songs = [M.Song(t, list(a)) for t, a in M.DEFAULT_SONGS]
    found, missing = M.run_lookup(songs, T.fake_searcher, 10, lambda _m: None)
    M.save_outputs(found, missing, tmp, lambda _m: None)
    return os.path.join(tmp, "results.json")


def write_cfg(path: str, **over) -> str:
    cfg = {"title": "T", "subtitle": "S", "accent": "#111", "accent2": "#222",
           "playlist_id": "", "privacy": "UNLISTED"}
    cfg.update(over)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh)
    return path


def render_check(path: str):
    """実ブラウザで開いて、注入されたタグやダイアログが無いことを確かめる。

    playwright が無い環境（CI など）では None を返してスキップする。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    if not os.path.exists(exe):
        return None

    dialogs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=exe)
        pg = b.new_page()
        pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        pg.goto("file://" + os.path.abspath(path))
        pg.wait_for_timeout(300)
        counts = pg.evaluate("""() => ({
            imgs: document.querySelectorAll('img').length,
            scripts: document.querySelectorAll('script').length
        })""")
        b.close()
    counts["dialogs"] = len(dialogs)
    return counts


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="ytmtest-")
    try:
        results = make_results(tmp)

        section("1. 曲の照合 (ytm_playlist)")
        rc = subprocess.run([sys.executable, "test_offline.py"],
                            capture_output=True, text=True).returncode
        check(rc == 0, "test_offline.py が通る（MV/カラオケ/カバー/同名異曲を除外）")

        section("2. プレイリスト URL の抽出 (set_playlist)")
        for value, want in [
            ("https://music.youtube.com/playlist?list=PLabc1234567&si=x", "PLabc1234567"),
            ("https://www.youtube.com/playlist?list=PLxyz9876543210", "PLxyz9876543210"),
            ("PLbare1234567890", "PLbare1234567890"),
            ("", ""),
        ]:
            check(set_playlist.extract(value) == want, f"extract({value[:42]!r})")

        cfg = write_cfg(os.path.join(tmp, "p.json"))
        for value, want_rc, label in [
            ("https://youtu.be/x9p_t5-S_E4?si=abc", 1, "動画リンクを拒否"),
            ("https://www.youtube.com/watch?v=abcdefghijk", 1, "watch リンクを拒否"),
            ("https://music.youtube.com/playlist?list=TLGGabcdefghij", 1, "一時プレイリストを拒否"),
            ("!!!short!!!", 1, "不正な文字列を拒否"),
            ("https://music.youtube.com/playlist?list=PL" + "a" * 32, 0, "正しい ID を受理"),
        ]:
            r = subprocess.run([sys.executable, "set_playlist.py", "--config", cfg,
                                "--value", value], capture_output=True, text=True)
            check(r.returncode == want_rc, label)

        r = subprocess.run([sys.executable, "set_playlist.py", "--config", cfg,
                            "--value", "PLdWPcRyOJTek"], capture_output=True, text=True)
        check(r.returncode == 0 and "警告" in r.stdout, "短い ID は受理しつつ警告を出す")

        section("3. リダイレクトからの ID 抽出 (resolve_playlist)")
        for url, want in [
            ("https://www.youtube.com/watch?v=a&list=TLGGtest1234567890", "TLGGtest1234567890"),
            ("https://www.youtube.com/watch?v=a", ""),
            ("https://www.youtube.com/watch?v=a&list=short", ""),
        ]:
            check(resolve_playlist.extract_list_id(url) == want, f"extract_list_id({url[-28:]})")

        section("4. プレイリストの差分計算 (sync_playlist)")
        for cur, tgt, wa, wr in [
            (["a", "b", "c"], ["a", "b", "c"], [], []),
            (["a", "b"], ["a", "b", "c"], ["c"], []),
            (["a", "b", "c"], ["a", "c"], [], ["b"]),
            ([], ["a"], ["a"], []),
            (["a", "a", "b"], ["a", "b"], [], []),
        ]:
            add, rem = sync_playlist.plan_changes(cur, tgt)
            check((add, rem) == (wa, wr), f"plan_changes({cur} -> {tgt})")

        section("5. プレイリスト照合 (verify_playlist)")
        c = verify_playlist.compare(["a", "b", "c"], ["a", "b", "c"])
        check(c["same_set"] and c["same_order"], "完全一致を検出")
        c = verify_playlist.compare(["c", "b", "a"], ["a", "b", "c"])
        check(c["same_set"] and not c["same_order"], "曲順違いを検出")
        c = verify_playlist.compare(["a", "b"], ["a", "b", "c"])
        check(c["missing"] == ["c"] and not c["extra"], "不足を検出")
        c = verify_playlist.compare(["a", "b", "z"], ["a", "b"])
        check(c["extra"] == ["z"] and not c["missing"], "余分を検出")

        section("6. ページ生成 (make_page)")
        # 6a. playlist_id 設定済み
        cfg_set = write_cfg(os.path.join(tmp, "set.json"),
                            playlist_id="https://music.youtube.com/playlist?list=PLzz1234567890&si=q")
        out_set = os.path.join(tmp, "set.html")
        rc = make_page.main(["--results", results, "--config", cfg_set, "--out", out_set])
        html_set = open(out_set, encoding="utf-8").read()
        check(rc == 0, "設定済みモードで生成できる")
        check("music.youtube.com/playlist?list=PLzz1234567890" in html_set,
              "ボタンがプレイリストを指す")
        check("PLzz1234567890&si=q" not in html_set, "URL の余計なパラメータを落とす")
        check(not re.search(r'https://www\.youtube\.com', html_set),
              "www.youtube.com が 1 つも無い")
        check("watch_videos" not in html_set, "watch_videos が残っていない")

        # 6b. 未設定（section 2 で cfg を書き換えているので新しく作る）
        cfg_unset = write_cfg(os.path.join(tmp, "unset.json"))
        out_unset = os.path.join(tmp, "unset.html")
        make_page.main(["--results", results, "--config", cfg_unset, "--out", out_unset])
        html_unset = open(out_unset, encoding="utf-8").read()
        check("プレイリストを作成" in html_unset, "未設定時はセットアップ導線を出す")
        check("music.youtube.com/watch?v=" in html_unset, "1曲目は YouTube Music を指す")

        # 6c. 共通
        for name, html in (("設定済み", html_set), ("未設定", html_unset)):
            check(not re.search(r"\$\{?[a-zA-Z_]+\}?", html), f"{name}: 未置換の変数が無い")
            check(html.count('class="track"') == 9, f"{name}: 曲数が一致")
            check("{save_url}" not in html, f"{name}: save_url が置換済み")
            check(html.count("</script>") == 1, f"{name}: script が閉じている")

        section("7. エスケープ (make_page)")
        cfg_evil = write_cfg(os.path.join(tmp, "evil.json"),
                             title='</title><script>alert(1)</script>',
                             subtitle='"><img src=x onerror=alert(2)>')
        out_evil = os.path.join(tmp, "evil.html")
        make_page.main(["--results", results, "--config", cfg_evil, "--out", out_evil])
        html_evil = open(out_evil, encoding="utf-8").read()
        head = html_evil[:html_evil.index("<style")]
        check("<script>alert(1)</script>" not in head, "title に生のタグが入らない")
        check("&lt;script&gt;" in head, "title はエスケープされている")
        check("<img" not in html_evil, "subtitle に生のタグが入らない")
        check("&lt;img" in html_evil, "subtitle はエスケープされている")
        check('content="">' not in html_evil, "属性から抜け出せない")

        rendered = render_check(out_evil)
        if rendered is None:
            print("  skip 実ブラウザでの検証（playwright 未導入）")
        else:
            check(rendered["imgs"] == 0, "ブラウザ: img 要素が生成されない")
            check(rendered["dialogs"] == 0, "ブラウザ: ダイアログが出ない")
            check(rendered["scripts"] == 1, "ブラウザ: script は本来の 1 個だけ")

        section("8. 供給元の判定 (mode)")
        for cfg_d, want in [
            ({}, "songs"),
            ({"playlist_id": "PL123"}, "playlist"),
            ({"playlist_id": "", "source": "playlist"}, "playlist"),
            ({"playlist_id": "PL123", "source": "songs"}, "songs"),
            ({"playlist_id": "PL1", "source": "でたらめ"}, "playlist"),
        ]:
            check(mode.detect(cfg_d) == want, f"detect({cfg_d}) -> {want}")

        section("9. プレイリストの取り込み (fetch_playlist)")
        sample = {
            "title": "dopamine",
            "tracks": [
                {"videoId": "aaaaaaaaaaa", "title": "One",
                 "artists": [{"name": "A"}, {"name": "B"}],
                 "album": {"name": "Alb"}, "duration": "3:00"},
                {"videoId": None, "title": "削除済み", "artists": []},
                {"videoId": "bbbbbbbbbbb", "title": "Two",
                 "artists": [{"name": "C"}], "album": None, "duration": "4:00"},
            ],
        }
        res = fetch_playlist.to_results(sample, "PLxyz")
        check(len(res["found"]) == 2, "videoId の無い曲を除外する")
        check(res["found"][0]["artists"] == "A, B", "複数アーティストを連結する")
        check(res["found"][1]["album"] == "", "アルバム未設定でも壊れない")
        check(res["playlist_title"] == "dopamine", "プレイリスト名を取り込む")
        check(res["urls"] == ["https://music.youtube.com/playlist?list=PLxyz"],
              "URL がプレイリストを指す")
        check(res["missing"] == [], "playlist モードに missing は無い")

        # 取り込んだ結果がそのままページ生成に通ること
        rj = os.path.join(tmp, "fetched.json")
        with open(rj, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
        cfg_pl = write_cfg(os.path.join(tmp, "pl.json"),
                           playlist_id="PLxyz", source="playlist", title="dopamine")
        out_pl = os.path.join(tmp, "pl.html")
        check(make_page.main(["--results", rj, "--config", cfg_pl, "--out", out_pl]) == 0,
              "取り込んだ結果からページを生成できる")
        html_pl = open(out_pl, encoding="utf-8").read()
        check("music.youtube.com/playlist?list=PLxyz" in html_pl, "ボタンがそのプレイリスト")
        check(html_pl.count('class="track"') == 2, "曲数がプレイリストと一致")
        check("dopamine" in html_pl, "タイトルが反映される")
        check(not re.search(r"https://www\.youtube\.com", html_pl), "www.youtube.com が無い")

        section("10. 取り込み元の判定 (import_source)")
        for v, want in [
            ("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=x", "spotify"),
            ("spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "spotify"),
            ("https://music.youtube.com/playlist?list=PLdWPcRyOJTek", "ytmusic"),
            ("Closer - The Chainsmokers", "text"),
            ("", "empty"),
        ]:
            check(I.detect_kind(v) == want, f"detect_kind -> {want}")
        check(I.parse_spotify_id("https://open.spotify.com/playlist/ABC123?si=x") == "ABC123",
              "Spotify の ID 抽出")
        check(I.parse_spotify_id("https://open.spotify.com/track/ABC123") == "",
              "曲の URL は ID として取らない")

        section("11. 曲名リストの解釈 (import_source)")
        for line, want in [
            ("Closer / The Chainsmokers, Halsey", ("Closer", ["The Chainsmokers", "Halsey"])),
            ("Closer - The Chainsmokers", ("Closer", ["The Chainsmokers"])),
            ("Closer — The Chainsmokers", ("Closer", ["The Chainsmokers"])),
            ("Cold Water - Major Lazer feat. Justin Bieber",
             ("Cold Water", ["Major Lazer", "Justin Bieber"])),
            ("1. Faded - Alan Walker", ("Faded", ["Alan Walker"])),
            ("Cheap Thrills\tSia", ("Cheap Thrills", ["Sia"])),
            ("Paris", ("Paris", [])),
            ("# コメント", None),
        ]:
            check(I.parse_line(line) == want, f"parse_line({line[:38]!r})")
        check(I.parse_line("The Chainsmokers - Closer", swap=True)
              == ("Closer", ["The Chainsmokers"]), "swap で順序反転")

        spotify_items = [
            {"track": {"name": "Closer",
                       "artists": [{"name": "The Chainsmokers"}, {"name": "Halsey"}]}},
            {"track": None},
            {"track": {"name": None, "artists": []}},
            {"track": {"name": "Faded", "artists": [{"name": "Alan Walker"}]}},
        ]
        check(I.tracks_from_spotify_items(spotify_items)
              == [("Closer", ["The Chainsmokers", "Halsey"]), ("Faded", ["Alan Walker"])],
              "Spotify の削除済み/ローカル曲を除外")

        # 生成した songs.txt を既存パーサが読み戻せること
        st = os.path.join(tmp, "imported.txt")
        with open(st, "w", encoding="utf-8") as fh:
            fh.write(I.to_songs_txt([("Closer", ["The Chainsmokers", "Halsey"]),
                                     ("Paris", [])], "test"))
        back = M.load_songs(st)
        check(len(back) == 2, "生成した songs.txt を読み戻せる")
        check(back[0].artists == ["The Chainsmokers", "Halsey"], "アーティストが保持される")
        check(back[1].artists == [], "アーティスト無しも扱える")

        section("12. 上書き事故の防止 (reset_target)")
        new_cfg, prev = reset_target.reset(
            {"playlist_id": "PLexisting", "source": "playlist", "title": "dopamine"})
        check(new_cfg["playlist_id"] == "", "取り込み時に playlist_id を外す")
        check(new_cfg["source"] == "songs", "songs モードに切り替える")
        check(new_cfg["previous_playlist_id"] == "PLexisting", "元の ID を控える")
        check(new_cfg["title"] == "dopamine", "他の設定は残す")
        n2, p2 = reset_target.reset({"playlist_id": "", "source": "songs"})
        check("previous_playlist_id" not in n2 and p2 == "", "未設定なら控えない")

        section("13. 文字列正規化 (ytm_playlist)")
        for got, want in [
            (M.norm("Don't Let Me Down"), "dont let me down"),
            (M.norm("It Ain’t Me"), "it aint me"),
            (M.norm("MØ"), "mo"),
            (M.norm("A & B"), "a and b"),
            (M.base_title("Closer (feat. Halsey)").strip(), "Closer"),
        ]:
            check(got == want, f"norm -> {want!r}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILS:
        print(f"失敗 {len(FAILS)} 件:")
        for f in FAILS:
            print("  -", f)
        return 1
    print("すべて成功しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
