# compress_overview v1.0

## System

You are given the Stage 2 compressed conversation log (all chunks already condensed). Generate a single **「全体サマリ (overview)」** section that goes at the top of the final output, allowing a future AI to grasp the entire session in 1-2 minutes without reading the detailed log below.

## User

Generate the overview section. Strict rules:

**Output format**

Start with the exact heading `## ⭐ 全体サマリ (Stage 3)` and use the following structure with exact heading text:

```
## ⭐ 全体サマリ (Stage 3)

### セッション概要
(2-3 文)。何を、どこまでやったか。何件のターンか。

### 主要トピック (時系列)
1. **<トピック名>** (ターン X-Y): <1-2 行で何を扱ったか>
2. ...

### 採用された決定事項
- <決定 1> (ターン X 参照)
- ...

### 採用されなかった案・却下理由
- <案>: <理由 1 行>
- ...

### 重要なファイル変更
- `<path>`: <変更内容 1 行>
- ...

### 未解決事項 / 次アクション
- <未解決 1>
- ...

### 重要な発見・気付き
- <発見 1>: <なぜ重要か>
- ...
```

**Rules**
- 各セクションは内容がなければそのセクション自体を省略してよい (見出しと「(該当なし)」を残すのは禁止)
- ターン番号への参照は `ターン X` または `ターン X-Y` 形式
- 全体で 300-600 行を目安に
- ファイル名・関数名・数値は元のまま (絶対変更しない)
- ユーザーの嗜好・優先順位が読み取れる場合は「決定事項」に含める
- 「重要な発見」は技術的・業務的洞察 (例: 「LLM は漢字↔カナの自動解決ができる」「不成立勧誘 3 件のパターンを発見」)

**Never do**
- 詳細ログを複製しない (詳細は下に既に圧縮版がある)
- 推測で内容を埋めない (圧縮ログにない情報は書かない)
- 自分のコメンタリー (「興味深い」「重要だ」など主観評価) を入れない
- 「今後の改善」「TODO 整理」など、元ログにない新規アクションは作らない

**Compressed log to process**

```markdown
{{COMPRESSED_LOG}}
```

Output the overview section now. Begin directly with `## ⭐ 全体サマリ (Stage 3)`. No preamble, no explanation.
