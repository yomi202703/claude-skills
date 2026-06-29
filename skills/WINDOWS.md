# Windows 共有 — 配布手順と移植性メモ

このリポジトリ(`~/.claude/skills`)を Windows へ渡すための送り手側メモ。
windows-share skill のプリフライト監査(2026-06-30)の結果を反映している。

## 配布物の作り方

クローンではなく `git archive` でバンドルを作る。`.gitattributes` の `export-ignore`
により、Windows で動かない skill・開発専用ドキュメント・作者専用ツールが自動で外れる。

```
# 1) 先に作業ツリーの変更をコミットする(archive はコミット済みツリーを固める)。
git add -A && git commit -m "..."

# 2) Windows 向けバンドルを生成。
git archive -o skills-windows.zip HEAD
```

未コミットのまま試すなら `git archive --worktree-attributes HEAD | tar -t` で中身だけ確認できる。
クローンでは `export-ignore` は効かない(除外したいならこの archive 経路を使う)。

## 移植性の階層

配布される skill(Windows 可搬)
- 文書系(方法論・プロンプト)中心の大多数は OS 非依存。
- Python 実行系(ai-wiki / xlsx-router / work-report / pdf-to-md / html-deck / review-server /
  zeitgeist / factcheck)は `Path.home()` / `expanduser` / `os.environ` 経由でパス可搬。
- 改行は `.gitattributes` で LF 固定(`setup.sh` の CRLF 破壊を防止)。

配布されるが注意が要る
- chatgpt-web / gemini-web — Chrome パスを OS 判定で解決するよう修正済み。Windows でも
  Chrome がインストール済み + 各サービスに手動ログイン済みなら動く。
- deadcode — `setup.sh` は `brew` 前提で Windows では自動セットアップ不可。ast-grep 等を
  winget/choco/手動で入れれば skill 本体(dead-code 検出)は動く。
- ai-wiki 等の起動手順に出る `python3` は Windows では `python` / `py` に読み替える。

配布から除外(`export-ignore`、Windows で根本的に動かない)
- atlas — osascript/AppleScript で ChatGPT Atlas を駆動(Mac 専用)。
- claude-desktop — macOS Accessibility API / pyobjc(Mac 専用)。
- antigravity — `open -a` + Mac アプリへの CDP(Mac 専用)。
- recall — `/Users/ivymee/Projects/recall` を絶対パス参照(別マシン固定。recall 本体を用意し
  パスを書き換えれば復活可能)。
- html-deck/scripts/anonymize_sample.py — 作者ホームパス固定の一回限り変換ツール。

## 検証していないこと(W1)

「Windows で実際に動くか」は実機がないため未検証。上記は静的監査の結論であり、
runtime の pass/fail は受領側で確認すること。
