# atlas — TODO

_未来 / 実行キュー。Active(いま着手可) と Deferred(ブロック中・解除トリガを名指す) のみ。_

## Active

（なし）

## Deferred

- 層3ブリッジを opencode(+Gemma) 向けに配布形へ包む。候補: (a) ask.py を小さな MCP サーバで包み `ask_chatgpt` ツール化、(b) プレーンCLI＋README で shell ツールから叩かせる、(c) 両方。対象は「Claude を持たず Gemma API + ChatGPT ログインだけ有る人」。本体は純 Python+osascript で既に harness 非依存ゆえ層2(トークン抽出)は不要。[user が配布形(a/b/c)を決めたとき]

## メモ

- 層2(セッショントークン再利用 = backend-api 直叩き)は Claude Code の auto-mode 分類器が credential-harvesting として遮断。これは Claude 側ガードで技術的不能ではないが、回避実装はしない方針。やるなら持ち主本人の手動 or 層1(APIキー)。
- Enable JS 手順(pref `browser.allow_javascript_apple_events=true`)は配布先の各マシンで一度きり必要。SKILL.md 参照。
