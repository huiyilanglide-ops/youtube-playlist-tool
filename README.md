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

## 他サービスのプレイリストを取り込む

Spotify のプレイリスト URL、曲名の羅列、YouTube Music のプレイリスト URL のいずれかを
渡すと、同じ内容のプレイリストを自分の YouTube Music 側に作れます。

[Run workflow](https://github.com/huiyilanglide-ops/youtube-playlist-tool/actions/workflows/playlist.yml)
の **取り込み元** 欄に貼るだけです。

| 貼るもの | 例 | 必要なもの |
|---|---|---|
| Spotify のプレイリスト | `https://open.spotify.com/playlist/...` | Secret 2 つ（下記） |
| 曲名の羅列 | `Closer - The Chainsmokers`（改行区切り） | なし |
| YouTube Music のプレイリスト | `https://music.youtube.com/playlist?list=...` | なし |

曲名の羅列は、どのサービスからコピーしても大体そのまま通ります。

```
1. Closer - The Chainsmokers
2. Faded — Alan Walker
Cold Water - Major Lazer feat. Justin Bieber
Cheap Thrills	Sia
Paris
```

連番、`-` / `—` / タブ / `/` 区切り、`feat.` の展開に対応しています。
「アーティスト - 曲名」の順で書かれている場合は `import_source.py --swap` を使ってください。

取り込んだあとは通常どおり、各曲の YouTube Music の**楽曲（Art Track）**を検索して
特定します。MV・カバー・カラオケ・同名異曲は除外されます。

> **取り込むと `playlist_id` は自動で外れます。** 残したまま進むと、取り込んだ曲で
> 既存プレイリストを上書きしてしまうためです。元の ID は `previous_playlist_id` に
> 控えるので、戻したい場合はそこから復元できます。

### Spotify の設定（初回だけ・無料）

[developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) でアプリを作り、
**Client ID** と **Client secret** を
[Secrets](https://github.com/huiyilanglide-ops/youtube-playlist-tool/settings/secrets/actions)
に `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` として登録します。

ユーザーのログインや同意は不要です（公開プレイリストを読むだけ）。
Google の OAuth と違い、値を 2 つコピーするだけで終わります。

## 2 つのモード

`page.json` の `source` で、ページに載せる曲目をどこから取るかが決まります。

| `source` | 曲目の供給元 | 向いている場面 |
|---|---|---|
| `playlist` | **既存プレイリストの実物** | 手持ちのプレイリストを共有したい |
| `songs` | `songs.txt` を検索した結果 | 曲名リストからプレイリストを作りたい |

未指定なら、`playlist_id` があれば `playlist`、無ければ `songs` になります。

### playlist モード

`fetch_playlist.py` がプレイリストを取得し、その中身から曲目リストを作ります。
**ページの表示と実際の中身が原理的にずれません。** プレイリスト側で曲を足し引きすれば、
次の実行でページも自動で追従します。`songs.txt` は使いません。

このモードでも `verify_playlist.py` は実行します。プレイリストを独立に取り直して
生成結果と突き合わせるため、取り込み処理の回帰チェックになります。

### songs モード

`songs.txt` の曲を検索して videoId を集めます。
`verify_playlist.py` が「ページの曲目」と「プレイリストの中身」を突き合わせ、
食い違っていればジョブサマリーと `verify_result.json` に差分を出します。

検証結果はいずれのモードでも `verify_result.json` に記録されます。

## プレイリスト作成を自動化する（推奨・初回だけ設定）

認証情報を登録しておくと、ワークフローが **YouTube Music に本物のプレイリストを
作成・更新**します。`songs.txt` を変えれば中身も自動で追従します。
YouTube 側で「保存」する手作業は不要になります。

プレイリスト ID は変えずに差分だけ反映するので、**共有リンクは切れません**。

### 1. Google Cloud で OAuth クライアントを作る

[console.cloud.google.com](https://console.cloud.google.com) をスマホのブラウザで開いて:

1. プロジェクトを作成
2. **YouTube Data API v3** を有効化
3. **OAuth 同意画面** → 外部 → テストユーザーに自分の Google アカウントを追加
4. **認証情報** → 認証情報を作成 → **OAuth クライアント ID**
   → アプリケーションの種類は **「テレビとリミット入力デバイス」**
5. 表示された **クライアント ID** と **クライアント シークレット** を控える

### 2. トークンを取る（Colab でできます）

[colab.research.google.com](https://colab.research.google.com) で新規ノートブックを作り、
`XXX` / `YYY` を差し替えて実行します。

```python
!pip install -q ytmusicapi
!curl -sLO https://raw.githubusercontent.com/huiyilanglide-ops/youtube-playlist-tool/claude/youtube-music-playlist-url-mvqupl/ytm_auth.py
!python ytm_auth.py --client-id "XXX" --client-secret "YYY"
```

URL とコードが表示されるので、ブラウザで承認してください。
承認が終わると JSON が 1 行で出力されます。

> **この JSON は YouTube アカウントへのアクセス権そのものです。**
> 公開の場所（Issue、SNS、Actions のログ）には絶対に貼らないでください。

### 3. GitHub に Secret を 3 つ登録

[Settings → Secrets and variables → Actions](https://github.com/huiyilanglide-ops/youtube-playlist-tool/settings/secrets/actions)
→ **New repository secret**

| 名前 | 中身 |
|---|---|
| `YTM_CLIENT_ID` | 手順 1 のクライアント ID |
| `YTM_CLIENT_SECRET` | 手順 1 のクライアント シークレット |
| `YTM_OAUTH_JSON` | 手順 2 で出力された JSON（1 行まるごと） |

Secret はリポジトリが public でも中身は公開されません。
このワークフローは `push`（指定ブランチ）と手動実行でしか動かず、
fork からの PR には Secret が渡らないため、外部から悪用される経路はありません。

### 4. 実行

[Run workflow](https://github.com/huiyilanglide-ops/youtube-playlist-tool/actions/workflows/playlist.yml)
を押すだけです。プレイリストが作成され、その ID が `page.json` に自動でコミットされ、
ランディングページのボタンが `music.youtube.com/playlist?list=...` になります。

公開範囲は `page.json` の `privacy` で変えられます（`UNLISTED` / `PUBLIC` / `PRIVATE`）。
既定は `UNLISTED`（リンクを知っている人だけ見られる）です。

### 設定しない場合

認証情報が無ければこのステップは自動でスキップされ、これまでどおり
「YouTube で一度保存 → ID を Actions のフォームに貼る」手順で運用できます。

## 共有用ランディングページ

ワークフローが実行されるたびに、スマートリンク風のページを生成して
GitHub Pages に公開します。

```
https://huiyilanglide-ops.github.io/youtube-playlist-tool/
```

### 最初に一度だけ: Pages を有効にする

ワークフローの権限では Pages を自動で有効化できないため、
最初の 1 回だけ手動で設定してください。

1. [Settings → Pages](https://github.com/huiyilanglide-ops/youtube-playlist-tool/settings/pages) を開く
2. **Build and deployment** の **Source** を **GitHub Actions** にする
3. Actions タブで **Run workflow** を押す

未設定のあいだも検索とプレイリスト URL の生成は普通に動きます。
公開だけがスキップされ、サマリーに案内が出ます。
生成済みの HTML は Artifacts の `playlist-results` → `site/index.html` から取り出せます。

ページ内のリンクは**すべて `music.youtube.com`** です。
`www.youtube.com`(= YouTube アプリ側)には飛ばしません。

- 大きいボタン → プレイリストを YouTube Music で開く
- 曲名をタップ → その曲を YouTube Music で開く
- Android は `intent://` で `com.google.android.apps.youtube.music` を名指しして起動し、
  アプリが無ければブラウザ版 YouTube Music に戻ります
- iOS はユニバーサルリンクでアプリに切り替わります
- Instagram や LINE のアプリ内ブラウザではアプリに切り替われないため、警告を表示します

### リンクの決まり方

| 条件 | ボタンのリンク |
|---|---|
| `page.json` に `playlist_id` あり | `music.youtube.com/playlist?list=...`（プレイリスト全体） |
| まだ無い | `music.youtube.com/watch?v=...`（1曲目）＋ セットアップ案内 |

**YouTube Music は「その場かぎりのプレイリスト」を開けません。**
`watch_videos` は YouTube 専用の仕組みで、`music.youtube.com` に投げても
`www.youtube.com` に転送されます。一時プレイリスト（`TLGG...`）も同様です。
そのため保存済みプレイリストの ID が無いあいだは、プレイリストのふりをせず
1曲目を開く動作にしています。

`resolve_playlist.py` が解決した一時 ID は、ボタンには使わず
セットアップ案内の「保存用リンク」にだけ使います。

見た目は `page.json` で変えられます。

| キー | 用途 |
|---|---|
| `title` | ページの見出し |
| `subtitle` | 見出しの下の説明 |
| `accent` / `accent2` | グラデーションの 2 色 |
| `playlist_id` | 保存済みプレイリストの ID(下記) |

### アプリで開くボタンを有効にする

`watch_videos` の URL は毎回その場かぎりのプレイリストを作る仕組みです。
共有用の固定リンクにするには、一度だけ保存して ID を控える必要があります。

1. 公開ページの「YouTube Music で開く」を押す
2. プレイリスト名の横の **「保存」** をタップ
3. 保存されたプレイリストを開き、URL の `list=` 以降をコピー
   （`PL` から始まる文字列。URL をまるごと貼っても構いません）
4. `page.json` の `playlist_id` に貼り付けて commit

これでワークフローが再実行され、ページのボタンが
`https://music.youtube.com/playlist?list=...` に切り替わります。

## スマホから実行する(PC が無いとき)

### 方法 1: GitHub Actions(おすすめ・タップだけ)

このリポジトリの **Actions** タブ → 左の **「プレイリスト URL 生成」** →
右上の **「Run workflow」** をタップするだけです。1 分ほどで終わります。

終わったら実行結果を開くと、**Summary** に

- タップできるプレイリストのリンク
- 曲名 / アーティスト / videoId の一覧
- 見つからなかった曲

が表示されます。コピー用の URL も置いてあります。

曲を変えたいときは、GitHub の画面で `songs.txt` を編集して commit するだけです。
push をきっかけにワークフローが自動で再実行されます。

### 方法 2: Google Colab(ブラウザで実行)

[colab.research.google.com](https://colab.research.google.com) を開き、
新しいノートブックに次を貼り付けて実行(▶)します。

```python
!pip install -q ytmusicapi
!curl -sLO https://raw.githubusercontent.com/huiyilanglide-ops/youtube-playlist-tool/claude/youtube-music-playlist-url-mvqupl/ytm_playlist.py
!curl -sLO https://raw.githubusercontent.com/huiyilanglide-ops/youtube-playlist-tool/claude/youtube-music-playlist-url-mvqupl/songs.txt
!python ytm_playlist.py --songs songs.txt
```

### 方法 3: Termux(Android)

```bash
pkg install python git -y
git clone https://github.com/huiyilanglide-ops/youtube-playlist-tool
cd youtube-playlist-tool
pip install ytmusicapi
python ytm_playlist.py --songs songs.txt
```

### スマホで URL を開くときの注意

`watch_videos` のリンクは YouTube アプリが横取りして正しく開けないことがあります。
うまくいかない場合はリンクを長押しして **ブラウザで開く**、または
ブラウザの **PC 版サイトを見る** をオンにしてください。

再生が始まったら「保存」でライブラリに入れておくと、YouTube Music 側の
ライブラリからも参照できます(ライブラリは両者で共有されます)。

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
- `site/index.html` — 共有用ランディングページ

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
