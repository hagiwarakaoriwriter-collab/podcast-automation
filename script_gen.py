"""調査結果から「経営者の言語化図鑑」のポッドキャスト台本を生成する"""

import json
import os
import time
from google import genai
from google.genai import types

from config import (
    PODCAST_TITLE,
    SPEAKER_HOST, SPEAKER_ASSISTANT,
    RESEARCH_MODEL, RESEARCH_MODEL_FALLBACK,
    RETRY_WAIT_SECONDS, MAX_RETRIES,
    OUTPUT_DIR,
)


def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if not text:
        try:
            parts = response.candidates[0].content.parts
            text = "".join(p.text for p in parts if getattr(p, "text", None))
        except Exception:
            text = ""
    return text or ""


def _call_script_api(model: str, prompt: str, api_key: str) -> str:
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
    """調査データから「経営者の言語化図鑑」の台本を生成する"""
    executive = research_data.get("executive_name", "不明")

    prompt = f"""以下は今日取り上げる経営者の発言データです。
これをもとに、日本語ポッドキャスト「{PODCAST_TITLE}」の台本を作成してください。

## 番組コンセプト
経営者の象徴的な発言を1つ取り上げ、その言葉選びの裏にあるブランディング戦略や意図を、
**ブランディング編集者・社外CBOの視点**で深掘りする番組です。
リスナーは経営者本人・広報担当者・編集ライター・キャリアに関心のあるビジネスパーソン。

## 話者設定
- **{SPEAKER_HOST}**（女性、ブランディング編集者・社外CBO）
  - 冷静で知性的、本質を見抜く視点
  - 心理学・キャリア心理学・社会学・対人コミュニケーション論などの専門知見を自然に織り交ぜる
  - 編集者として「なぜこの言葉を選んだのか」を読み解く
- **{SPEAKER_ASSISTANT}**（男性、ある経営者の広報担当）
  - 素朴な疑問やリスナー目線の質問を投げかけるアシスタント役
  - 「広報の現場ではどう活かせるか」を引き出す
  - 軽快で親しみやすいトーン

## 構成（5分程度・合計1500〜2000文字）
1. **オープニング**: 今日取り上げる経営者の紹介と、なぜ今話題なのか
2. **取り上げる発言の引用**: 正確な発言と発言の場面・文脈
3. **言葉の分解**: なぜこの言葉を選んだのか（編集者目線で語彙・構文・トーンを分析）
4. **ブランディング戦略の解読**: 誰に何を伝えているのか
   - 心理学・キャリア心理学・社会学・対人コミュニケーション論などの専門的知見を必ず1つ以上引用する
   - 例: 「これはアドラー心理学でいう〇〇に近く...」「社会学者の◯◯が提唱した概念で言えば...」
5. **リスナーへの転用ポイント**: 経営者・広報担当・編集者が真似できる視点

## 注意
- 引用する専門知見は実在する理論・概念にしてください（捏造禁止）
- {SPEAKER_HOST}が深い分析、{SPEAKER_ASSISTANT}が質問・要約・共感、というリズム
- 「えーと」「あのー」など不自然なフィラーは避ける
- 自然な会話の流れで、専門用語は使ったら必ず噛み砕く

## 調査データ
{json.dumps(research_data, ensure_ascii=False, indent=2)}

## 出力形式（JSONのみ・Markdownコードブロック不要）
{{
  "executive_name": "{executive}",
  "title": "エピソードタイトル（30字以内・キャッチー）",
  "script": "{SPEAKER_HOST}: 発話\\n{SPEAKER_ASSISTANT}: 発話\\n... の形式"
}}

台本テキストは必ず「{SPEAKER_HOST}: 〜\\n{SPEAKER_ASSISTANT}: 〜\\n」の繰り返しで記述してください。"""

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
    script_data["executive_name"] = executive

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = f"{OUTPUT_DIR}/script.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)
    print(f"台本を {out_path} に保存しました")
    print(f"  タイトル: {script_data.get('title')}")
    print(f"  台本文字数: {len(script_data.get('script', ''))}")

    return script_data
