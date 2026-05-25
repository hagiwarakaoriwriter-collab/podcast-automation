# Podcast 番組設定
PODCAST_TITLE = "経営者の言語化図鑑"

# 話者・声設定
# 秋カヲリ（女性、ブランディング編集者・社外CBO、本質を見抜く分析役）
# 佐藤（男性、経営者の広報担当、素朴な疑問を投げかけるアシスタント役）
SPEAKER_HOST = "秋カヲリ"
SPEAKER_ASSISTANT = "佐藤"
VOICE_HOST = "Aoede"        # 女性
VOICE_ASSISTANT = "Charon"  # 男性

# モデル設定
RESEARCH_MODEL = "gemini-2.5-flash-lite"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
RESEARCH_MODEL_FALLBACK = "gemini-2.5-flash"
TTS_MODEL_FALLBACK = "gemini-3.1-flash-tts-preview"

# Google Drive（固定値）
DRIVE_FOLDER_NAME = "経営者の言語化図鑑"

# TTS 1回あたりの最大文字数
TTS_CHUNK_MAX_CHARS = 1800

# リトライ設定
RETRY_WAIT_SECONDS = 60
MAX_RETRIES = 3

# ファイルパス
OUTPUT_DIR = "output"
COVERED_TOPICS_FILE = "covered_topics.json"  # 過去取り上げた経営者・発言の履歴
