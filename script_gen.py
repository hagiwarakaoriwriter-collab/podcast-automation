"""調査結果から 5 分程度のポッドキャスト台本を生成する"""

import json
import os
import time
from google import genai
from google.genai import types

from config import (
    SPEAKER_MALE, SPEAKER_FEMALE,
    RESEARCH_MODEL, RESEARCH_MODEL_FALLBACK,
    RETRY_WAIT_SECONDS, MAX_RETRIES,
    OUTPUT_DIR,
)


def _call_script_api(model: str, prompt: str, api_key: str) -> str:
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    text = getattr(response, "text", None)
    if not text:
        try:
            parts = response.candidates[0].content.parts
            text = "".join(p.text for p in parts if getattr(p, "text", None))
        except Exception:
            text = ""
    if not text or not text.strip():
        print(f"[{model}] 空のレスポンスを受け取りました")
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


def generate_script(research_data: dict, api_key: str) -> dict:
    """調査データから台本を生成して script.json を返す"""
    version = research_data.get("version", "不明")

    prompt = f"""以下の Claude Code バージョン {version} の調査データをもとに、
日本語のポッドキャスト台本を作成してください。

## 調査データ
{json.dumps(research_data, ensure_ascii=False, indent=2)}

## 台本の要件
- 話者は {SPEAKER_MALE}（男性、テック系ポッドキャストのメインホスト）と
  {SPEAKER_FEMALE}（女性、エンジニアの視点から鋭い質問をするコホスト）の2名
- 合計 5 分程度（1500〜2000 文字程度）
- 自然な会話形式で、リスナーにとって分かりやすく面白い内容
- 専門用語は適宜説明する
- Claude Code を使っている開発者や興味を持つ人に向けた内容

## 出力形式
以下の JSON 形式のみ出力してください（Markdown コードブロック不要）：
{{
  "version": "{version}",
  "title": "エピソードタイトル",
  "script": "台本テキスト（{SPEAKER_MALE}: 〜\\n{SPEAKER_FEMALE}: 〜\\n の形式）"
}}

台本テキストは「{SPEAKER_MALE}: 発話内容\\n{SPEAKER_FEMALE}: 発話内容\\n」の繰り返しで記述してください。"""

    print(f"台本生成を開始します（モデル: {RESEARCH_MODEL}）")

    try:
        text = _with_retry(
            lambda: _call_script_api(RESEARCH_MODEL, prompt, api_key),
            label=RESEARCH_MODEL,
        )
    except Exception as e:
        print(f"メインモデルでの台本生成に失敗: {e}")
        print(f"フォールバックモデル {RESEARCH_MODEL_FALLBACK} でリトライします...")
        text = _with_retry(
            lambda: _call_script_api(RESEARCH_MODEL_FALLBACK, prompt, api_key),
            label=RESEARCH_MODEL_FALLBACK,
        )

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    script_data = json.loads(text)
    script_data["version"] = version

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = f"{OUTPUT_DIR}/script.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
    print(f"台本を {out_path} に保存しました")
    print(f"台本文字数: {len(script_data.get('script', ''))}")

    return script_data
