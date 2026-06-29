# Windows 共有 — 移植性メモ

このリポジトリ(`~/.claude/skills`)を Windows の Claude Code へ `git clone` / `pull` で
渡すときの送り手側メモ。windows-share skill のプリフライト監査(2026-06-30)の結果。

## 前提: clone なので全 skill が降りる

共有は `git clone` / `pull`。全 skill がそのまま Windows 側に入る。自動除外はしない
(`git archive` 専用の `export-ignore` は clone では無効なため、属性での除外は不採用)。
clone でも効くのは改行正規化(`.gitattributes` の `eol=lf`)だけで、これは checkout 時に
適用され `setup.sh` の CRLF 破壊を防ぐ。

このため、下記「Windows で動かない skill」も Windows 側 Claude の skill 一覧に載る。
誤って起動すると失敗する。手動で使わない運用で回避する(必要なら後から各マシンで削除)。

## 移植性の階層

そのまま動く(Windows 可搬)
- 文書系(方法論・プロンプト)中心の大多数は OS 非依存。
- Python 実行系(ai-wiki / xlsx-router / work-report / pdf-to-md / html-deck / review-server /
  zeitgeist / factcheck)は `Path.home()` / `expanduser` / `os.environ` 経由でパス可搬。

注意が要る
- chatgpt-web — Chrome パスを OS 判定で解決するよう修正済み。Windows でも Chrome が
  インストール済み + ChatGPT に手動ログイン済みなら動く。
- aftercare の deadcode パス — `reference/deadcode/setup.sh` は `brew` 前提で Windows では自動セットアップ不可。ast-grep 等を
  winget/choco/手動で入れれば dead-code 検出は動く。
- ai-wiki 等の起動手順に出る `python3` は Windows では `python` / `py` に読み替える。

Windows で動かない(降りてくるが起動しないこと)
- atlas — osascript/AppleScript で ChatGPT Atlas を駆動(Mac 専用)。
- claude-desktop — macOS Accessibility API / pyobjc(Mac 専用)。
- antigravity — `open -a` + Mac アプリへの CDP(Mac 専用)。
- recall — `/Users/ivymee/Projects/recall` を絶対パス参照(別マシン固定。recall 本体を用意し
  パスを書き換えれば動く)。
- html-deck/scripts/anonymize_sample.py — 作者ホームパス固定の一回限り変換ツール(skill 本体は動く)。

## 検証していないこと(W1)

「Windows で実際に動くか」は実機がないため未検証。上記は送り手側・静的監査の結論であり、
runtime の pass/fail は受領側で確認すること。
