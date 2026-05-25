"""ポッドキャスト「経営者の言語化図鑑」自動生成メインスクリプト"""

import os
import re
import sys
from datetime import datetime, timezone, timedelta

from config import OUTPUT_DIR, PODCAST_TITLE
from research import research_trending_executive, save_covered_topic
from script_gen import generate_script
from tts import generate_audio
from drive_upload import upload_to_drive

JST = timezone(timedelta(hours=9))


def get_today_jst() -> str:
    override = os.environ.get("DATE_OVERRIDE", "").strip()
    if override:
        print(f"日付オーバーライド: {override}")
        return override
    return datetime.now(JST).strftime("%Y-%m-%d")


def _sanitize_for_folder(name: str) -> str:
    """フォルダ名に使えない文字を除去"""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "unknown"


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = get_today_jst()
    print(f"=== 「{PODCAST_TITLE}」生成開始: {today} ===")

    # ── STEP 1: 今日のトレンド経営者を調査 ────────────────────────────
    try:
        print(f"\n--- STEP 1: 今日のトレンド経営者を調査 ---")
        research_data = research_trending_executive(today, api_key)
    except Exception as e:
        print(f"調査失敗: {e}", file=sys.stderr)
        _log_partials("調査失敗")
        sys.exit(1)

    executive_name = research_data.get("executive_name", "unknown")

    # ── STEP 2: 台本生成 ─────────────────────────────────────────
    try:
        print(f"\n--- STEP 2: 台本生成 ---")
        script_data = generate_script(research_data, api_key)
    except Exception as e:
        print(f"台本生成失敗: {e}", file=sys.stderr)
        _log_partials("台本生成失敗")
        sys.exit(1)

    # ── STEP 3: 音声生成 ─────────────────────────────────────────
    try:
        print(f"\n--- STEP 3: 音声生成 ---")
        script_text = script_data.get("script", "")
        mp3_path = generate_audio(script_text, api_key)
    except Exception as e:
        print(f"音声生成失敗: {e}", file=sys.stderr)
        _log_partials("音声生成失敗")
        sys.exit(1)

    # ── STEP 4: Google Drive アップロード ─────────────────────────
    try:
        print(f"\n--- STEP 4: Google Drive アップロード ---")
        required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            print(f"警告: {missing} が設定されていないため Drive アップロードをスキップします")
        else:
            folder_name = f"{today}_{_sanitize_for_folder(executive_name)}"
            link = upload_to_drive(mp3_path, folder_name)
            print(f"Drive リンク: {link}")
    except Exception as e:
        print(f"Drive アップロード失敗（MP3 は保存済み）: {e}", file=sys.stderr)
        _log_partials("Driveアップロード失敗")
        sys.exit(1)

    # ── STEP 5: 取り上げた経営者・発言を記録 ──────────────────────
    save_covered_topic({
        "date": today,
        "executive_name": executive_name,
        "statement": research_data.get("statement", ""),
        "title": script_data.get("title", ""),
    })
    print(f"\n=== 完了: 「{script_data.get('title')}」を生成しました ===")


def _log_partials(reason: str) -> None:
    print(f"途中成果物を output/ に保存済み（理由: {reason}）")
    for name in ["research.json", "script.json"]:
        path = f"{OUTPUT_DIR}/{name}"
        if os.path.exists(path):
            print(f"  保存済み: {path}")


if __name__ == "__main__":
    main()
