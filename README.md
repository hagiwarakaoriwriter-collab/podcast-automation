# Claude Code Podcast Automation

Claude Code の最新バージョン変更点を毎日自動調査し、日本語ポッドキャスト（MP3）を生成して Google Drive にアップロードするシステムです。

---

## セットアップ

### 1. Gemini API キーの取得

[Google AI Studio](https://aistudio.google.com/app/apikey) で API キーを発行し、GitHub Secrets に登録してください。
- Secret 名: **`GEMINI_API_KEY`**

---

### 2. Google OAuth クライアント ID の作成

1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. 新規プロジェクトを作成（既存プロジェクトでも可）
3. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuth クライアント ID」を選択
4. アプリケーションの種類: **ウェブアプリケーション**
5. 承認済みリダイレクト URI に以下を追加:
   ```
   https://developers.google.com/oauthplayground
   ```
6. 作成後に表示される「クライアント ID」と「クライアント シークレット」をメモ

GitHub Secrets に登録:
- Secret 名: **`GOOGLE_CLIENT_ID`** ← クライアント ID
- Secret 名: **`GOOGLE_CLIENT_SECRET`** ← クライアント シークレット

---

### 3. OAuth スコープの有効化

Google Cloud Console で **Google Drive API** を有効にしてください。

---

### 4. リフレッシュトークンの取得（OAuth 2.0 Playground）

> **重要**: 本番環境でリフレッシュトークンを取得してください。テスト環境のままだと 7 日でトークンが失効します。

1. [OAuth 2.0 Playground](https://developers.google.com/oauthplayground) を開く
2. 右上の歯車アイコン → 「Use your own OAuth credentials」をオン
3. 手順 2 で作成したクライアント ID とシークレットを入力
4. Step 1 のスコープ入力欄に以下を貼り付けて「Authorize APIs」:
   ```
   https://www.googleapis.com/auth/drive.file
   ```
5. Google アカウントでログインして許可
6. Step 2 で「Exchange authorization code for tokens」を押す
7. `refresh_token` の値をコピー

GitHub Secrets に登録:
- Secret 名: **`GOOGLE_REFRESH_TOKEN`** ← リフレッシュトークン

---

## GitHub Secrets の設定順序

| 順番 | Secret 名 | 説明 |
|------|-----------|------|
| 1 | `GEMINI_API_KEY` | Gemini API キー（Google AI Studio で取得） |
| 2 | `GOOGLE_CLIENT_ID` | OAuth クライアント ID |
| 3 | `GOOGLE_CLIENT_SECRET` | OAuth クライアント シークレット |
| 4 | `GOOGLE_REFRESH_TOKEN` | OAuth リフレッシュトークン（Playground で取得） |

設定場所: GitHub リポジトリ → Settings → Secrets and variables → Actions → New repository secret

---

## 実行方法

### 定期実行（自動）

毎日 JST 6:00（UTC 21:00）に自動で実行されます。

### 手動実行

1. GitHub リポジトリの「Actions」タブを開く
2. 「Daily Podcast Generation」を選択
3. 「Run workflow」ボタンを押す
4. `date_override`（任意）: 日付を上書きしたい場合に入力（例: `2026-05-22`）

---

## 出力ファイル

| ファイル | 説明 | git 管理 |
|----------|------|----------|
| `output/research.json` | 調査結果 | あり |
| `output/script.json` | 台本 | あり |
| `output/chunk_*.wav` | 音声チャンク（中間） | なし |
| `output/podcast.mp3` | 最終 MP3 | なし |
| `researched_versions.json` | 調査済みバージョン履歴 | あり |

MP3 は Google Drive の `Podcasts/v{バージョン}_{日付}/` フォルダにアップロードされます。

---

## 使用モデル

| 用途 | メインモデル | フォールバック |
|------|-------------|----------------|
| 調査 | `gemini-2.5-flash-lite` | `gemini-2.5-flash` |
| 音声合成 | `gemini-2.5-flash-preview-tts` | `gemini-3.1-flash-tts-preview` |
