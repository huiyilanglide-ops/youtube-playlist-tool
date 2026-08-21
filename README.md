# YouTube Music プレイリスト URL 生成ツール

指定した曲の YouTube Music **「楽曲」(Art Track)** の `videoId` を自動取得し、
`watch_videos` 形式の URL を 1 本生成します。

## MV ではなく「楽曲」を取る仕組み

`ytmusicapi` の `search(filter="songs")` **だけ**を使います。
これは YouTube Music の「楽曲」タブに相当し、返るのは Art Track の `videoId` です。
ミュージックビデオは `filter="videos"` 側にしか出ないため、MV の ID は原理的に混入しません。

さらに二重の安全策として、

- 検索結果の `resultType` が `song` のものだけを候補にする
- カラオケ / カバー / トリビュート / Nightcore / インスト等は強く減点して除外する
- リミックス / ライブ / アコースティック等の別バージョンは減点し、選ばれた場合は「※要確認」を付ける
- 曲名とアーティスト名を照合し、同名異曲(例: *Let Me Love You* の DJ Snake 版と Mario 版)を取り違えないようにする

を入れています。

認証は不要です(検索のみ使用)。

## 使い方(Windows)

`run.bat` をダブルクリックするだけです。以下を自動で行います。

1. Python を探す。無ければ `winget install --id Python.Python.3.12 -e` で導入
2. `pip install ytmusicapi`
3. `ytm_playlist.py` を実行

> winget で Python を入れた直後は PATH がそのウィンドウに反映されません。
> その場合はウィンドウを閉じて `run.bat` をもう一度実行してください。

### 手動で実行する場合

```bat
winget install --id Python.Python.3.12 -e --source winget
pip install ytmusicapi
python ytm_playlist.py
```

## 曲リストの変更

`songs.txt` を編集して `--songs` を付けて実行します。

```bat
python ytm_playlist.py --songs songs.txt
```

書式は 1 行 1 曲:

```
曲名 / アーティスト1, アーティスト2
```

`/` でアーティストを分けて書くと照合精度が上がります。曲名だけでも動きます。

## オプション

| オプション | 既定値 | 説明 |
|---|---|---|
| `--songs PATH` | (内蔵リスト) | 曲リストのファイル |
| `--limit N` | `10` | 1 クエリあたりの検索件数 |
| `--out-dir DIR` | `out` | 結果の保存先 |
| `--no-files` | off | ファイルを保存しない |
| `--timeout SEC` | `20` | 1 リクエストのタイムアウト秒 |

## 出力

画面表示に加えて `out/` に保存されます。

- `results.csv` — 曲名 / アーティスト / videoId の一覧(Excel で開ける BOM 付き UTF-8)
- `playlist_url.txt` — 生成された URL
- `results.json` — 生の結果(要確認理由なども含む)

URL の形式:

```
https://www.youtube.com/watch_videos?video_ids=ID1,ID2,...
```

`videoId` が 50 件を超える場合は `watch_videos` の上限に合わせて URL を分割します。

## ロジックの検証(ネットワーク不要)

```bat
python test_offline.py
```

ダミーの検索結果を流し込み、MV・カラオケ・カバー・リミックス・同名異曲を掴まないこと、
見つからない曲が正しく振り分けられること、URL が正しく組み立てられることを確認します。

## つながらないとき

`music.youtube.com` に到達できない場合は、全曲を延々と再試行せず数秒で中断し、
確認すべき点(ファイアウォール / プロキシ / VPN など)を表示して終了コード `1` を返します。
`videoId` が 1 件も取れていない状態で URL を出すことはありません。

会社や学校のネットワークでは `music.youtube.com` が遮断されていることがあります。
その場合は自宅のネットワークやモバイル回線で実行してください。

## 補足

- 生成した URL を最初に開くと YouTube 側で一時的なプレイリストが作られます。
  恒久的に残したい場合は、再生画面から「保存」でライブラリのプレイリストにしてください。
- 検索結果は地域や時期によって変わることがあります。`※要確認` が付いた曲は
  `out/results.csv` で曲名・アルバム名を確認してください。
