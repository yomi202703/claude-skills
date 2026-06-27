# glm-web decisions

Append-only ADR. Why a choice was made and what happened.

## 2026-06-27 第2の CN ネイティブ橋として新設

chat.z.ai（智谱 GLM）を CDP で駆動する橋として追加。当初は qwen-web と並ぶ第2の CN ネイティブ種出し源（相互参照で高信頼）として位置づけた。共有 Chrome（port 9333・`~/.gemini-chrome`）に同居、無料・API キー不要。プロファイル共有で既にログイン済みだった（サインイン不要）。

## 2026-06-27 セレクタは実 DOM probe で確定

editor `textarea#chat-input`、send `button.sendMessageButton`、user `div.chat-user`、assistant `div.chat-assistant`、本文 `.markdown-prose`（混雑/エラー泡は無いので turn の innerText をフォールバック）。生成シグナルは送信ボタンの不在（生成中は `button.sendMessageButton` が DOM から消え、完了で戻る＝qwen と逆）。混雑時は "Model is currently at capacity" を verbatim 返す＝タブでモデルを切り替えて再試行。

## 2026-06-27 CN ネイティブ知識から外し、コーディング役へ転換

検証で GLM は CN 文脈固有語を字面から西側モデル的に再構成して外すと判明（例: 赛博对账 を qwen のみ正解、GLM は誤読）。よって CN 一次/辺境ソースの種出しは qwen-web に一本化し、glm-web はそこから外す。glm-web の役割を GLM-5.x が強いコーディング/エンジニアリング（実装・デバッグ・コードレビューの非相関意見）に再定義。description もこの線に改訂。cn-search/reference/sources.md の種出し記述・「2モデル一致＝高信頼」運用もこれに合わせて廃止。
