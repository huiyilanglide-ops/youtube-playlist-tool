@echo off
REM ============================================================
REM  YouTube Music プレイリスト URL 生成ツール (Windows 用)
REM  Python が無ければ winget で導入し、ytmusicapi を入れて実行する。
REM
REM  このファイルは Shift_JIS(cp932)で保存されています。
REM  編集する場合は文字コードを変えないでください。
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY="

REM --- 1. 既存の Python を探す ---------------------------------
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)

REM --- 2. 無ければ winget で導入 -------------------------------
if not defined PY (
    echo Python が見つかりません。winget で導入します...
    where winget >nul 2>nul
    if errorlevel 1 (
        echo.
        echo [エラー] winget が使えません。
        echo   https://www.python.org/downloads/windows/ から Python を導入し、
        echo   インストーラの "Add python.exe to PATH" に必ずチェックを入れてください。
        echo.
        pause
        exit /b 1
    )

    winget install --id Python.Python.3.12 -e --source winget --accept-source-agreements --accept-package-agreements
    if errorlevel 1 (
        echo.
        echo [エラー] Python の導入に失敗しました。
        pause
        exit /b 1
    )

    REM winget 直後は PATH が未更新のため探し直す
    py -3 --version >nul 2>nul && set "PY=py -3"
    if not defined PY (
        for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
            if exist "%%D\python.exe" set "PY=%%D\python.exe"
        )
    )
    if not defined PY (
        echo.
        echo Python は導入されましたが、PATH がこのウィンドウに反映されていません。
        echo このウィンドウを閉じて、run.bat をもう一度実行してください。
        echo.
        pause
        exit /b 0
    )
)

echo 使用する Python:
%PY% --version

REM --- 3. ytmusicapi を導入 ------------------------------------
echo.
echo ytmusicapi を確認/導入します...
%PY% -m pip install --upgrade pip >nul 2>nul
%PY% -m pip install ytmusicapi
if errorlevel 1 (
    echo.
    echo [エラー] ytmusicapi の導入に失敗しました。ネットワーク設定を確認してください。
    pause
    exit /b 1
)

REM --- 4. 実行 -------------------------------------------------
REM  Python 側は UTF-8 で出力するので、ここでコードページを切り替える。
echo.
chcp 65001 >nul
%PY% ytm_playlist.py %*
set "RC=%ERRORLEVEL%"
chcp 932 >nul

echo.
echo 終了コード: %RC%
echo 結果は out\results.csv と out\playlist_url.txt にも保存されています。
pause
exit /b %RC%
