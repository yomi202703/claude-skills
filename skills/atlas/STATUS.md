# atlas — STATUS

_現況スナップショット。毎セッション書き直す。_

最終更新: 2026-06-26

## 動いているもの

- 層3ブリッジ完成・検証済。CDP 不要・API 課金ゼロ・既存ログイン再利用で、ローカルから ChatGPT(および前面タブの任意ページ)を操作できる。
- `scripts/atlas_js.py`: 前面タブで JS 実行する汎用プリミティブ。
- `scripts/ask.py`: ChatGPT に質問→返信回収（`--new` 新規会話 / `--timeout` 待ち時間）。複数ターン連続可(同一会話に積み上がる)を実機確認。
- 実証済の到達範囲: タブの read(URL/DOM/書きかけ)、自分の Drive ファイルの単発ダウンロード(認証付き)。

## 前提(この環境で成立済)

- pref `browser.allow_javascript_apple_events=true` を該当プロファイルの Preferences に直書き済(有効化メニューは Atlas UI から削除されているため)。再起動後も定着。
- Atlas→端末の Automation 権限は承認済。

## 未着手 / 保留

- 配布形(opcode+Gemma 向け MCP/CLI 包装)は Deferred。TODO 参照。
- 層2(セッショントークン再利用)は不採用。decisions 2026-06-26 参照。
