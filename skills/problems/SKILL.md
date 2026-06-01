Base directory for this skill: /Users/ivymee/.claude/skills/problems

# problems

プロジェクトの **問題点 (defect / gap / inconsistency / concern)** を全 doc から
時系列で抽出し、現在の解決状況まで判定する 4-gemma パイプライン。

「課題 = task (やる予定)」ではなく **「課題 = 問題点 (うまく行ってない所)」** を
扱う。進捗 (progress) は問題への解決過程として timeline に統合される。

## When to invoke

- `loop` skill から呼ばれる (主用途)
- プロジェクトの「問題点とその経緯」を 1 枚に整理したい時
- 単独で `.loop/problems.{json,md}` だけ更新したい時

## When NOT to invoke

- 単一の TODO リストが欲しいだけ → 別途 grep で十分
- コード単体監査 → `gemma-worker`
- 統合ブリーフィング → `loop`

## What it does (4-gemma pipeline)

```
全 doc → A1 (progress lens) + A2 (problem lens) で並列 occurrence 要約
       → B: events を problem 単位でクラスタリング、timeline 構築
       → C: コード/実態と照合、latest_state 確定、discrepancy 検出
       → D: discrepancy の原因分析
       → .loop/problems.{json,md}
```

LLM call: doc 数 × 2 (A1+A2) + 3 (B/C/D)。

## Output

`.loop/problems.json`:
```json
{
  "problems": [
    {
      "problem_id": "<8-char>",
      "title": "...",
      "timeline": [
        {"date": "ISO", "doc": "...", "lens": "problem|progress",
         "kind": "提起|分析|決定|実装|再発|未解決|解説", "summary": "..."}
      ],
      "latest_state": "open|resolved|discrepancy",
      "latest_summary": "...",
      "code_evidence": [...],
      "discrepancy_analysis": "..." | null
    }
  ],
  "unclassified_events": [...],
  "generated_at": "ISO",
  "stats": {...}
}
```

`.loop/problems.md`: 上記を読みやすく整形。各 problem section + timeline + latest_state バッジ。

## CLI

```bash
# 初回 (loop bootstrap で代替可)
problems run --repo <PATH>

# 段階実行 (デバッグ用、中間結果が .loop/_stages/ に cache される)
problems run --repo <PATH> --stage extract        # A1+A2 まで
problems run --repo <PATH> --stage consolidate    # B まで
problems run --repo <PATH> --stage verify         # C まで
problems run --repo <PATH> --stage analyze        # D まで (default = full)

# 中間 cache を無視して再実行
problems run --repo <PATH> --no-cache
```

## Output schema rules

- 全 summary に grounding: バッククォートで file path / symbol を引用
- timeline 内 event の date は ISO8601、doc mtime か doc 内記述日付
- latest_state は決定論的に最終 event の kind から導出 (LLM 任せにしない部分)
- **エスカレーション / ボール所在判定は `/constraints` skill の責務**。本 skill は課題抽出+進捗状態判定 (open/resolved/discrepancy) に限定
- **意図的後回し (internal_defer) は `/progress` skill の責務** (将来)
