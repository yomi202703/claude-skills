# zeitgeist decisions（append-only）

過去エントリは書き換えない。なぜその選択をしたか／何が起きたかを日付順に積む。

## 2026-06-26 Antigravity（Gemini）を「広さ補助」火元に採用

採用: CN コミュニティの未編集の現場知・B站/YouTube の動画圏・Google 側という、この環境の WebSearch（US 寄り）と WebFetch で届きにくい死角を埋める補助火元として、Antigravity 経由の Gemini を WebSearch と同列の広さレイヤーに追加。安い・速いので並列で気軽に撃てる点が、裏取りしない発散フェーズと噛み合う。

位置づけの線引き: 鮮度バックボーンには入れない。LLM 返答は信頼できる per-item timestamp を持たず velocity を自前計算できないため、生の velocity 表に混ぜると「他社の単眼ランキング」と同種の混入になる。広さレイヤー限定。

実走で確定した作法: inline capture は当てにしない（ブリッジの DOM-stability ヒューリスティックが書き込み完了前に返る／sentinel を取りこぼす実例を2回観測）。`~/.claude/skills/zeitgeist/.cache/gemini.json` への file-handoff＋ファイル存在リトライ確認＋valid JSON 確認が安定チャネル。受け入れテストで 12秒・無承認・items 一致を確認。

承認の本当の仕組み（誤りの訂正を含む）:
- 誤って一度「trustedFolders.json の TRUST_FOLDER に入っていれば無承認」と結論したが、これは撤回する。trustedFolders はワークスペースを開く信頼（VS Code 型）であって、エージェントのツール実行の自動承認ではない。最初の「成功」は実際にはユーザーが承認ボタンを押していた。
- 正しくは: 承認は `~/.gemini/config/config.json` の `userSettings.globalPermissionGrants.allow` 配列のパス単位 allowlist が決める。形式は `write_file(<abs>)` / `read_file(<abs>)` / `command(<name>)`。グローバル（プロジェクト外会話に適用）。
- 設定経路: Settings → Permissions → File Permissions → File Writes に `~/.claude/skills/zeitgeist/.cache/gemini.json` の allow ルールを追加して実現。承認ダイアログの「Yes, and always allow when not in a project」は本来欲しい範囲より広い（プロジェクト外の書き込み全部）ので採らず、パス1件スコープに限定した。
- 含意: 今後は UI を毎回叩かず、config.json の allow 配列に `write_file(...)` を1行 append すれば宣言的に承認不要パスを足せる。

反映先: SKILL.md「広さ補助 = Antigravity（Gemini）」節に作法・前提を記載済み。
