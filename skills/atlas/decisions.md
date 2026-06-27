# atlas — decisions

_追記型 ADR 台帳。なぜその選択をしたか／何が起きたか。過去エントリは書き換えない。_

## 2026-06-26 atlas スキル新設・層3ブリッジ採用

経緯: 「Antigravity が CDP ブリッジで成立するなら ChatGPT Atlas も操作できるのでは」というユーザー着想の検証から。

判明した事実(実機):
- Atlas は CDP(remote debugging)を封鎖。デフォルトプロファイルは Chrome 136+ 制約でフラグ無視、別プロファイル指定でもポートが開かず＝ビルド/ポリシーで無効化。Antigravity 式の「ただ乗り」は不成立。
- 一方 Atlas は Chrome 由来の AppleScript 辞書を温存。`get URL of active tab` 等が通り、`execute ... javascript` も実装済（pref ゲートのみ）。
- pref `browser.allow_javascript_apple_events` を有効化するメニュー項目は Atlas UI から削除済(ラベル文字列もバイナリに無し)。よって Preferences ファイル直書きで有効化(Atlas 終了中に書く必要あり。Secure Preferences には戻されず定着)。

決定:
- 層3(AppleScript で前面タブに JS 注入→DOM 操作)を本線に採用。CDP 不要・無料・ログイン再利用を満たす。
- 完了判定は「stop ボタン消滅＋テキスト安定」のヒューリスティック。長文はファイルハンドオフを推奨(SKILL.md)。

## 2026-06-26 層2(セッショントークン再利用)は won't-do

- 層2 = web が内部で叩く backend-api を Bearer トークンで直叩きする案。堅牢だが、`/api/auth/session` からのトークン抽出が Claude Code の auto-mode 分類器に credential-harvesting として遮断された。
- これは Claude 側ハーネスのガードで技術的不能ではない。が、回避実装はしない方針(資格情報の裸扱い・ToS グレー・内部 API 依存という根の懸念は実行者を替えても消えないため)。
- 必要なら持ち主本人の手動 or 層1(API キー)で。層3 で実害(セレクタ頻繁破綻)が出てから再検討。

## 2026-06-26 自動再有効化スクリプト(enable_js.py)は同梱しない

- pref を立て直すブートストラップの同梱が、self-modification ガードに遮断された(UI から外された機能の再有効化スクリプトの永続化)。妥当な歯止めと判断。
- 代替: 有効化は SKILL.md に手動手順として明記。現環境では pref 定着済ゆえ運用に支障なし。剥がされたら手順を再実行。

## 2026-06-26 能力境界の運用線

- read(タブ閲覧)・自分の単発取得は即実行。送信/削除/一括/他人のリソース等の outward・不可逆操作は明示確認を挟む。資格情報抽出はそもそも遮断。
- 被害半径は「ログイン中の全サービス」。自分専用なら低リスク、他者配布/非信頼エージェント経由で一気に増大。配布検討時の前提として記録。
