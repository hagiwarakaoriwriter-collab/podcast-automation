"""Claude Code 最新バージョンの変更点を Gemini + Google Search Grounding で調査する"""

import json
import time
import requests
from google import genai
from google.genai import types

from config import (
    RESEARCH_MODEL, RESEARCH_MODEL_FALLBACK,
    CLAUDE_CODE_RELEASES_URL,
    RETRY_WAIT_SECONDS, MAX_RETRIES,
    OUTPUT_DIR, TRACKED_VERSIONS_FILE,
)


def get_latest_claude_code_version() -> tuple[str, str]:
    """GitHub Releases API から最新バージョンと変更内容を取得する"""
    print("GitHub Releases API から Claude Code の最新バージョンを取得中...")
    headers = {"Accept": "application/vnd.github+json"}
    response = requests.get(CLAUDE_CODE_RELEASES_URL, headers=headers, timeout=30)
    response.raise_for_status()
    releases = response.json()
    if not releases:
        raise ValueError("リリース情報が見つかりませんでした")
    latest = releases[0]
    version = latest.get("tag_name", "").lstrip("v")
    body = latest.get("body", "")
    print(f"最新バージョン: {version}")
    return version, body


def load_tracked_versions() -> list[str]:
    """調査済みバージョン一覧を読み込む"""
    try:
        with open(TRACKED_VERSIONS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("versions", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_tracked_version(version: str) -> None:
    """調査済みバージョンを記録する"""
    tracked = load_tracked_versions()
    if version not in tracked:
        tracked.append(version)
    with open(TRACKED_VERSIONS_FILE, "w", encoding="utf-8") as f:
        json.dump({"versions": tracked}, f, ensure_ascii=False, indent=2)
    print(f"バージョン {version} を調査済みとして記録しました")


def _call_research_api(model: str, prompt: str, api_key: str) -> str:
    """Gemini + Google Search Grounding で調査を実行する"""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return _extract_text(response)


def _extract_text(response) -> str:
    """response.text が None の場合も text part を直接取り出す"""
    text = getattr(response, "text", None)
    if text:
        return text
    try:
        parts = response.candidates[0].content.parts
        return "".join(p.text for p in parts if getattr(p, "text", None))
    except Exception:
        return ""


def _with_retry(func, label: str) -> str:
    """429/503 エラーに対してリトライする"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func()
        except Exception as e:
            err = str(e)
            if attempt < MAX_RETRIES and ("429" in err or "503" in err or "RESOURCE_EXHAUSTED" in err):
                print(f"[{label}] レート制限エラー（試行 {attempt}/{MAX_RETRIES}）。{RETRY_WAIT_SECONDS}秒後にリトライ...")
                time.sleep(RETRY_WAIT_SECONDS)
            else:
                raise


def research_claude_code(version: str, release_body: str, api_key: str) -> dict:
    """指定バージョンの Claude Code 変更点を調査して research.json を返す"""
    prompt = f"""Claude Code バージョン {version} の変更点・新機能・改善点について、
以下のリリースノートを参考にしながら、Google Search で最新情報を検索し、
ポッドキャストの台本に使える詳細な情報をまとめてください。

## リリースノート
{release_body}

## 調査すること
- 主要な新機能と使い方
- バグ修正と改善点
- 開発者への影響（ユースケース）
- 技術的な詳細（実装面での変化）
- ユーザーへの恩恵

## 出力形式
JSON 形式で以下の構造にしてください：
{{
  "version": "{version}",
  "summary": "全体の要約（100文字程度）",
  "new_features": ["機能1", "機能2", ...],
  "bug_fixes": ["修正1", "修正2", ...],
  "improvements": ["改善1", "改善2", ...],
  "developer_impact": "開発者への影響の説明",
  "user_benefits": "ユーザーへの恩恵の説明",
  "technical_details": "技術的な詳細"
}}

JSON のみ出力してください。Markdown コードブロックは不要です。"""

    print(f"バージョン {version} の調査を開始します（モデル: {RESEARCH_MODEL}）")

    try:
        text = _with_retry(
            lambda: _call_research_api(RESEARCH_MODEL, prompt, api_key),
            label=RESEARCH_MODEL,
        )
    except Exception as e:
        print(f"メインモデルでの調査に失敗: {e}")
        print(f"フォールバックモデル {RESEARCH_MODEL_FALLBACK} でリトライします...")
        text = _with_retry(
            lambda: _call_research_api(RESEARCH_MODEL_FALLBACK, prompt, api_key),
            label=RESEARCH_MODEL_FALLBACK,
        )

    # JSON 抽出
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    research_data = json.loads(text)
    research_data["version"] = version

    # output/research.json に保存
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = f"{OUTPUT_DIR}/research.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(research_data, f, ensure_ascii=False, indent=2)
    print(f"調査結果を {out_path} に保存しました")

    return research_data
