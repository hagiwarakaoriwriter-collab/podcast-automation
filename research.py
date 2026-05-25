"""今日トレンドの経営者・発言を Gemini + Google Search Grounding で調査する"""

import json
import os
import time
from google import genai
from google.genai import types

from config import (
    RESEARCH_MODEL, RESEARCH_MODEL_FALLBACK,
    RETRY_WAIT_SECONDS, MAX_RETRIES,
    OUTPUT_DIR, COVERED_TOPICS_FILE,
)


def load_covered_topics() -> list[dict]:
    """過去取り上げた経営者・発言の履歴を読み込む"""
    try:
        with open(COVERED_TOPICS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            return data.get("topics", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_covered_topic(topic: dict) -> None:
    """取り上げた経営者・発言を記録する（直近30件まで保持）"""
    topics = load_covered_topics()
    topics.append(topic)
    topics = topics[-30:]  # 直近30件のみ保持
    with open(COVERED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump({"topics": topics}, f, ensure_ascii=False, indent=2)
    print(f"取り上げた経営者: {topic.get('executive_name')} / 発言: {topic.get('statement', '')[:30]}...")


def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if not text:
        try:
            parts = response.candidates[0].content.parts
            text = "".join(p.text for p in parts if getattr(p, "text", None))
        except Exception:
            text = ""
    return text or ""


def _call_research_api(model: str, prompt: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    text = _extract_text(response)
    if not text or not text.strip():
        print(f"[{model}] 空のレスポンスを受け取りました")
        try:
            fr = response.candidates[0].finish_reason
            print(f"  finish_reason: {fr}")
        except Exception:
            pass
        raise ValueError("Gemini が空のテキストを返しました")
    return text


def _with_retry(func, label: str) -> str:
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


def research_trending_executive(date_str: str, api_key: str) -> dict:
    """今日のトレンド経営者と象徴的発言を1つ調査して research.json を返す"""
    covered = load_covered_topics()
    covered_summary = "\n".join(
        f"- {t.get('executive_name')}: {t.get('statement', '')[:50]}..."
        for t in covered[-30:]
    ) or "（過去履歴なし）"

    prompt = f"""今日（{date_str}）のSNS（X等）・ニュース・最近のインタビュー記事から、
**今話題になっている経営者**を1人選び、その人の**象徴的な発言を1つ**取り上げてください。

## 選定基準
- 直近1〜4週間以内のトレンド性のある発言（古すぎる名言は避ける）
- 経営哲学・組織観・人材観・キャリア観など「言語化」が興味深いもの
- ジャンルは日替わりで幅広く（IT/製造/小売/スタートアップ/海外含む可）

## 過去に取り上げた経営者・発言（重複を避ける）
{covered_summary}

## Google Search で調査すること
- その経営者の最新の発言（X投稿、インタビュー、決算会見、書籍など）
- 発言の正確な引用
- 発言の文脈（どんな場面で・誰に向けて・何を意図して）
- その経営者の経歴・スタイル・ブランディング戦略
- なぜ今その発言が注目されているか（トレンド背景）

## 出力形式（JSONのみ、Markdownコードブロック不要）
{{
  "executive_name": "経営者の氏名",
  "executive_title": "肩書（例: 〇〇株式会社 代表取締役）",
  "statement": "発言の正確な引用（1〜3文程度）",
  "source": "発言ソース（例: 2026年5月20日のX投稿、〇〇誌インタビューなど）",
  "context": "発言の背景・文脈（200〜300字）",
  "executive_background": "経営者の経歴・ブランディングの特徴（200〜300字）",
  "trend_relevance": "なぜ今この発言が話題か（150〜200字）",
  "key_themes": ["テーマ1（例: 人材観）", "テーマ2", "テーマ3"]
}}"""

    print(f"今日のトレンド経営者を調査中（モデル: {RESEARCH_MODEL}）...")

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

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    research_data = json.loads(text)
    research_data["date"] = date_str

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = f"{OUTPUT_DIR}/research.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(research_data, f, ensure_ascii=False, indent=2)
    print(f"調査結果を {out_path} に保存しました")
    print(f"  経営者: {research_data.get('executive_name')}")
    print(f"  発言: {research_data.get('statement', '')[:60]}...")

    return research_data
