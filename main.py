"""ポッドキャスト自動生成メインスクリプト"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

from config import OUTPUT_DIR, TRACKED_VERSIONS_FILE
from research import get_latest_claude_code_version, load_tracked_versions, save_tracked_version, research_claude_code
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


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = get_today_jst()
    print(f"=== ポッドキャスト生成開始: {today} ===")

    # ── STEP 1: 最新バージョン確認 ────────────────────────────────
    try:
        version, release_body = get_latest_claude_code_version()
    except Exception as e:
        print(f"バージョン取得失敗: {e}", file=sys.stderr)
        sys.exit(1)

    tracked = load_tracked_versions()
    if version in tracked:
        print(f"バージョン {version} は調査済みです。スキップします。")
        sys.exit(0)

    # ── STEP 2: 調査 ────────────────────────────────────────────
    try:
        print(f"\n--- STEP 2: バージョン {version} の調査 ---")
        research_data = research_claude_code(version, release_body, api_key)
    except Exception as e:
        print(f"調査失敗: {e}", file=sys.stderr)
        _commit_partials(version, today, "調査失敗")
        sys.exit(1)

    # ── STEP 3: 台本生成 ─────────────────────────────────────────
    try:
        print(f"\n--- STEP 3: 台本生成 ---")
        script_data = generate_script(research_data, api_key)
    except Exception as e:
        print(f"台本生成失敗: {e}", file=sys.stderr)
        _commit_partials(version, today, "台本生成失敗")
        sys.exit(1)

    # ── STEP 4: 音声生成 ─────────────────────────────────────────
    try:
        print(f"\n--- STEP 4: 音声生成 ---")
        script_text = script_data.get("script", "")
        mp3_path = generate_audio(script_text, api_key)
    except Exception as e:
        print(f"音声生成失敗: {e}", file=sys.stderr)
        _commit_partials(version, today, "音声生成失敗")
        sys.exit(1)

    # ── STEP 5: Google Drive アップロード ─────────────────────────
    try:
        print(f"\n--- STEP 5: Google Drive アップロード ---")
        # Drive 用の認証情報が揃っているか確認
        required = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
        missing = [k for k in required if not os.environ.get(k)]
        if missing:
            print(f"警告: {missing} が設定されていないため Drive アップロードをスキップします")
        else:
            link = upload_to_drive(mp3_path, version, today)
            print(f"Drive リンク: {link}")
    except Exception as e:
        print(f"Drive アップロード失敗（MP3 は保存済み）: {e}", file=sys.stderr)
        _commit_partials(version, today, "Driveアップロード失敗")
        sys.exit(1)

    # ── STEP 6: バージョンを調査済みとして記録 ──────────────────────
    save_tracked_version(version)
    print(f"\n=== 完了: バージョン {version} のポッドキャストを生成しました ===")


def _commit_partials(version: str, date: str, reason: str) -> None:
    """失敗時でも途中成果物の情報をログ出力する（実際の git commit は Actions ワークフローで行う）"""
    print(f"途中成果物を output/ に保存済み（理由: {reason}）")
    for name in ["research.json", "script.json"]:
        path = f"{OUTPUT_DIR}/{name}"
        if os.path.exists(path):
            print(f"  保存済み: {path}")


if __name__ == "__main__":
    main()
