# 話者・声設定（固定値）
SPEAKER_MALE = "田中"
SPEAKER_FEMALE = "鈴木"
VOICE_MALE = "Charon"
VOICE_FEMALE = "Aoede"

# モデル設定（固定値）
RESEARCH_MODEL = "gemini-2.5-flash-lite"
TTS_MODEL = "gemini-2.5-flash-preview-tts"
RESEARCH_MODEL_FALLBACK = "gemini-2.5-flash"
TTS_MODEL_FALLBACK = "gemini-3.1-flash-tts-preview"

# Google Drive（固定値）
DRIVE_FOLDER_NAME = "Podcasts"

# GitHub Releases API
CLAUDE_CODE_RELEASES_URL = "https://api.github.com/repos/anthropics/claude-code/releases"

# TTS 1回あたりの最大文字数
TTS_CHUNK_MAX_CHARS = 1800

# リトライ設定
RETRY_WAIT_SECONDS = 60
MAX_RETRIES = 3

# ファイルパス
OUTPUT_DIR = "output"
TRACKED_VERSIONS_FILE = "researched_versions.json"
