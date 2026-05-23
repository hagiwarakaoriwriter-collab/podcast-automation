"""台本を音声に変換して WAV チャンクと MP3 を生成する"""

import base64
import os
import subprocess
import time
import wave
from google import genai
from google.genai import types

from config import (
    SPEAKER_MALE, SPEAKER_FEMALE,
    VOICE_MALE, VOICE_FEMALE,
    TTS_MODEL, TTS_MODEL_FALLBACK,
    TTS_CHUNK_MAX_CHARS,
    RETRY_WAIT_SECONDS, MAX_RETRIES,
    OUTPUT_DIR,
)

# Gemini TTS の PCM 設定
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit


def split_script_into_chunks(script_text: str) -> list[str]:
    """台本を 1800 文字未満のチャンクに分割する（発話単位で区切る）"""
    lines = [line for line in script_text.split("\n") if line.strip()]
    chunks = []
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > TTS_CHUNK_MAX_CHARS:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line
        else:
            current_chunk = (current_chunk + "\n" + line).strip() if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk.strip())

    print(f"台本を {len(chunks)} チャンクに分割しました")
    for i, chunk in enumerate(chunks):
        print(f"  チャンク {i}: {len(chunk)} 文字")
    return chunks


def pcm_to_wav(pcm_data: bytes, wav_path: str) -> None:
    """PCM バイト列を WAV ファイルに書き出す"""
    with wave.open(wav_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm_data)


def _build_tts_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                speaker_voice_configs=[
                    types.SpeakerVoiceConfig(
                        speaker=SPEAKER_MALE,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=VOICE_MALE
                            )
                        ),
                    ),
                    types.SpeakerVoiceConfig(
                        speaker=SPEAKER_FEMALE,
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=VOICE_FEMALE
                            )
                        ),
                    ),
                ]
            )
        ),
    )


def _call_tts_api(model: str, chunk_text: str, api_key: str) -> bytes:
    """TTS API を呼び出して PCM バイト列を返す"""
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=chunk_text,
        config=_build_tts_config(),
    )
    audio_part = response.candidates[0].content.parts[0]
    inline_data = audio_part.inline_data.data
    # SDK バージョンによって bytes または base64 文字列が返る
    if isinstance(inline_data, (bytes, bytearray)):
        return bytes(inline_data)
    return base64.b64decode(inline_data)


def _with_retry(func, label: str) -> bytes:
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


def generate_audio(script_text: str, api_key: str) -> str:
    """台本全体から podcast.mp3 を生成してパスを返す"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    chunks = split_script_into_chunks(script_text)
    wav_files = []

    for i, chunk in enumerate(chunks):
        wav_path = f"{OUTPUT_DIR}/chunk_{i:03d}.wav"
        print(f"チャンク {i} の音声生成中（{len(chunk)} 文字）...")

        try:
            pcm = _with_retry(
                lambda c=chunk: _call_tts_api(TTS_MODEL, c, api_key),
                label=TTS_MODEL,
            )
        except Exception as e:
            print(f"メイン TTS モデルでの生成に失敗: {e}")
            print(f"フォールバック TTS モデル {TTS_MODEL_FALLBACK} でリトライします...")
            pcm = _with_retry(
                lambda c=chunk: _call_tts_api(TTS_MODEL_FALLBACK, c, api_key),
                label=TTS_MODEL_FALLBACK,
            )

        pcm_to_wav(pcm, wav_path)
        wav_files.append(wav_path)
        print(f"  → {wav_path} に保存しました")

    mp3_path = f"{OUTPUT_DIR}/podcast.mp3"
    _combine_wavs_to_mp3(wav_files, mp3_path)
    return mp3_path


def _combine_wavs_to_mp3(wav_files: list[str], mp3_path: str) -> None:
    """複数の WAV を FFmpeg で結合して MP3 に変換する"""
    if len(wav_files) == 1:
        cmd = [
            "ffmpeg", "-y",
            "-i", wav_files[0],
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            mp3_path,
        ]
    else:
        list_file = f"{OUTPUT_DIR}/filelist.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for wav in wav_files:
                f.write(f"file '{os.path.abspath(wav)}'\n")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_file,
            "-codec:a", "libmp3lame", "-qscale:a", "2",
            mp3_path,
        ]

    print("FFmpeg で WAV を MP3 に変換中...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg エラー:\n{result.stderr}")
    print(f"MP3 を {mp3_path} に保存しました")
