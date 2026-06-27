# qwen-web decisions

Append-only ADR. Why a choice was made and what happened.

## 2026-06-27 CN ネイティブ橋として新設

gemini-web / chatgpt-web は西側モデルの橋しかなく、CN ネイティブの非相関意見と cn-search の種出し実行役が欠けていた。chat.qwen.ai（通義千問）を CDP で駆動する橋として追加。Qwen は中文 web 訓練で CN 固有語の土地勘があり、cn-search の「定番外 CN 辺境ソース」種出しの主役。

## 2026-06-27 共有 Chrome に同居（無料・API キー不要）

gemini-web / chatgpt-web と同一インスタンス（port 9333・プロファイル `~/.gemini-chrome`）に Qwen を兄弟タブとして同居。署名済み web セッションを叩くだけで API トークン課金ゼロ。`cdp.py` は host `chat.qwen.ai` で target 解決、`new_tab`（Target.createTarget）でタブを起こす。

## 2026-06-27 セレクタは実 DOM probe で確定

推測で焼かず、ログイン後の実 DOM を probe して確定（2026-06 時点）：editor `textarea.message-input-textarea`、send `button.send-button`、生成中は send→`button.stop-button` にトグル（＝生成シグナル）、user `.qwen-chat-message-user`、assistant `.qwen-chat-message-assistant`、本文 `.response-message-content`。UI 変更時は cdp.py で再 probe して ask.py を更新。
