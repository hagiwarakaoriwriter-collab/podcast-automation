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
経営者の象徴的な発言を1つ取り上げ、その発言が**どんな印象を与えるか**を具体的に深掘り、
言葉選びの裏にあるブランディング戦略・無意識の構造を、
**ブランディング編集者・社外CBOの視点**で見立てる番組です。
リスナーは経営者本人・広報担当者・編集ライター・キャリアに関心のあるビジネスパーソン。

## 話者設定
- **{SPEAKER_HOST}**（女性、ブランディング編集者・社外CBO）
  - 冷静で知性的、本質を見抜く視点。当たり障りないことは絶対に言わない
  - 「言うて〇〇じゃないですか」「結局これって〇〇なんですよね」のように**踏み込んで断定する**
  - 比喩で印象を可視化する（例：「この人の言葉ってサウナの体験に近くて」「広告コピーじゃなく日記みたいな手触り」）
  - 心理学・キャリア心理学・社会学・対人コミュニケーション論などの専門知見を**実在する理論名・人物名つきで**引用する
  - 表面の発言ではなく、本人が無意識でやっている**構造**を言い当てる（リフレーミング）
- **{SPEAKER_ASSISTANT}**（男性、ある経営者の広報担当）
  - 軽快で親しみやすいトーン。秋カヲリさんの分析を「え、それってどういうこと？」と引き出す役
  - リスナーが「もうちょっと噛み砕いて聞きたい」と思った瞬間に質問する
  - 共感だけで終わらせず、「広報の現場で言うとこういう場面ですよね？」と具体に落とす

## 構成（5分程度・合計1500〜2000文字）

### ① オープニング（200字程度）
- 今日の経営者を紹介
- 「なぜ今この人を取り上げるのか」のトレンド背景
- 「で、実はこの人の今回の発言、私すごく気になっていて」と引き込む

### ② 発言の引用 & 第一印象（300字程度）
- 発言を正確に引用
- {SPEAKER_HOST}が**最初に受け取った印象を比喩で言語化**
  - 例：「これ読んだ瞬間、なんか湿度のある言葉だなって思ったんですよね」
  - 例：「これ、広告コピーじゃなくて、私信に近いんですよ」
- {SPEAKER_ASSISTANT}が「湿度のある言葉？」と引き取って深掘りを促す

### ③ 言葉の分解（400字程度）
- なぜこの語彙を選んだのか（編集者目線で具体的に）
  - 「〇〇」という単語を選ばずに「△△」と書いた選択の意味
  - 文末のトーン、主語の置き方、接続詞の使い方
- 「言うて、こういう書き方する経営者ってあんまりいないんですよ」のような相対化

### ④ 構造の見立て（500字程度）
- 表面の意味の裏にある**戦略・心理構造**を言い当てる
- **実在の専門知見を1つ以上引用**（必ず人物名・理論名を出す）
  - 例：「これって社会学者・宮台真司が言う『終わりなき日常』への態度表明にも見える」
  - 例：「心理学で言うと、ロジャーズの自己一致の概念に近くて」
  - 例：「キャリア理論で言えばクランボルツの計画的偶発性理論のスタンスですよね」
- 「だから何が起きるか」まで踏み込む（誰に届くか・どう信頼を獲得するか）
- ちょっと毒のある観察も歓迎（「言うて、これは下手するとブランディングが嫌味になる手前のギリギリのライン」）

### ⑤ リスナーへの転用ポイント（200字程度）
- 経営者・広報担当・編集者が**明日から真似できる具体的な視点**を1つ
- 抽象論ではなく「次のSNS投稿でこの構文を試してみてください」レベルの具体性

## 絶対に避けること（重要）
- 「素晴らしい」「興味深い」「学びがある」のような**当たり障りない褒め言葉**で終わる
- 「〜のようですね」「〜と言えるでしょう」のような**評論家ぶった距離感**
- 「えーと」「あのー」のフィラー
- 専門知見の捏造（必ず実在する理論・人物のみ）
- 抽象論で逃げる（「経営者の本気が伝わりますね」みたいな空疎な結論）

## 推奨する口調・リズム
- {SPEAKER_HOST}: 「〜じゃないですか」「言うて〜ですよね」「これって結局〜なんですよ」「私の見立てだと〜」
- {SPEAKER_ASSISTANT}: 「え、それってどういうこと？」「もうちょい噛み砕いてもらっていいですか」「広報の現場で言うと？」「あー、それヤバいですね」
- 2人のリズムは「深い分析 → 素朴な引き取り → さらに深く」の往復

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
