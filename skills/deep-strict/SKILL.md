---
name: deep-strict
description: 結論を後で再現・検証する必要がある重い web 調査。atomic claim 単位で独立 source 数を満たすまで裏取り (WebFetch 上限なし)、fact-checker による反対論サーチ、PROMOTE/HOLD/contested の confidence tier 付き構造化出力、~/.claude/plans/ に再現性ログを自動保存。技術選定・セキュリティ判断・論文ベースの設計決定など、後日「なぜこう判断したか」を辿る必要がある時に呼ぶ。
---

# deep-strict

固定パイプライン: **Phase 1a → 1b → 1c → 2 → 3 → 3.5 → 4 + 再現性ログ**。

WebFetch は claim 駆動（上限なし）。WebSearch も新規 URL 率 < 30% になるまで自由。判断は捏造で埋めず、`contested` / `single-source` / `unverified` タグで明示する。

## Phase 1a — 並列メタスイープ

Agent ツールで Explore 型 subagent を複数本並列起動。各 subagent への prompt:

```
WebSearchして「{クエリ}」。URL / title / 1行 snippet の表だけ返す。
```

クエリ設計:
- 時間アンカー: literal 2026-MM（"X 2026年5月" / "X May 2026" / "X 2026-05"）。
- 軸を変える:
  - 鮮度狙い: "X 2026年5月"
  - 視点違い: "X vs alternatives" / "X benchmark"
  - 否定形/限界: "X failure" / "X limitations" / "X 批判"
- 言語: 日本固有 = 日本語必須 / 学術・OSS・海外発 = 英語優先 / 両方該当 = 各軸を両言語

subagent 戻り値を本体 context に集約。

**Checkpoint**: 「検索クエリは網羅的か？欠けた軸はないか？」を自問し、欠けがあれば Phase 1a を 1 度だけ追補。

## Phase 1b — アンカー fetch（条件付き、最大 1 件）

バッファに以下があれば 1 件だけ WebFetch、無ければスキップ:
- タイトルに `survey` / `overview` / `awesome-` / `guide` / `comprehensive`
- 公式 doc のインデックス
- 発行日 1 年以上前のサーベイは対象外

## Phase 1c — Adversarial Sweep（**必須**）

```
あなたは fact-checker です。「{主張}」の真偽を中立的に検証してください。

検証すべきこと:
1. その主張が事実か（公式アナウンス・一次ソース）
2. 主張に対する批判・限界・反例があるか
3. 主張が誇張・未実装・不正確である可能性
4. 立場が異なる複数視点

WebSearch を以下のクエリで両言語(日+英)で実施 (YYYY-MM は literal 2026-MM、現在月で展開):
- "{topic} criticism 2026-MM"
- "{topic} limitations 2026-MM"
- "{topic} failed cases 2026-MM"
- "{topic} alternative beats 2026-MM"
- 「{topic} 批判 2026年MM月」「{topic} 限界 2026年MM月」

URL / title / 1行 snippet の表だけ返す。賛成・反対・不明を区別。最低 8 件。
肯定情報と否定情報の両方を集めてよい。事実検証が目的。
```

**Checkpoint**: 反対論が本当に独立 critique か（擁護記事内の小さな注意書きを critique と誤認していないか）を自問。**もし fact-checker が「賛成方向に固まった、反論なし」と返した場合、Phase 3 で明示的に「反証 fetch」を 1 件追加すること**（賛成バイアスを構造的に防ぐ）。

## Phase 2 — 未知語解決（必須）

Phase 1 結果を見て自問:
1. 自分が知らない固有名詞・術語はあるか
2. 「文脈から類推して既知扱い」していないか
3. 学習データ cutoff 以降の日付タグを持つソースはあるか

未知語を **網羅列挙** し、各項目が解決するまで WebSearch を追加。本数は内容駆動。並列実行可。

クエリには Phase 1a と同様に literal 2026-MM を必ず付ける。日付付きで結果が空 or 不十分な場合のみ、同クエリを日付なしで再実行する fallback を許可。

**Checkpoint**: 未解決語をリストアップして「これは本当に既知か、雰囲気で既知扱いしていないか」を再自問。

## Phase 3 — Atomic Claim Extraction + Per-Claim Corroboration

### Step 1: Atomic Claim 抽出

Phase 1+1c+2 の集約結果から、回答に含めうる atomic claim を列挙する。各 claim は:

- 単一の事実 / 主張 / 数値 / 判断であること
- それ単体で True/False が判定できること

各 claim に **stakes 等級** を付与:

- `high`: 結論の根幹（最低 **3 独立 primary source**）
- `medium`: 補強情報（最低 2 独立）
- `low`: 雑学・周辺（1 source で可）

「独立」とは: **異なる著者 / 異なる組織 / 異なる発信時期** の少なくとも 2 軸が違うこと。同じ author の別記事は独立ではない。

### Step 2: Per-Claim Fetch ループ（上限なし）

```
for each claim in atomic_claims:
    while supporting_sources(claim) < required_count(claim.stakes):
        next_url = pick_best_primary_source_for(claim)
        if next_url is None:
            mark claim as "single-source" or "unverified"
            break
        WebFetch(next_url)
        update supporting_sources(claim)
```

「pick best」の優先順位:
1. arxiv / openreview / 公式 doc / 公式リポジトリ
2. 当事者発信（GitHub 紐付き個人ブログ）
3. 公式リリースノート
4. 著名な独立メディア

**Checkpoint**: 各 claim の supporting_sources が本当に独立か（同じ著者 / 同じ組織の連投ではないか）を再自問。

抽出内容: ベンチ数値 / バージョン / 日付 / 相対表現（「現在は推奨されない」「以前は X だったが今は Y」）/ **対立点（Phase 1c の反対論との衝突）**。

## Phase 3.5 — Evidence Sufficiency Gate（ハードゲート）

- **Gap**: 問いの全側面に証拠があるか
- **Corroboration**: 各 claim が stakes に応じた独立 source 数を満たすか
- **Novelty**: 既知の事実ばかりになってないか
- **Redundancy**: 同じ情報の繰り返しになってないか
- **Relevance**: 証拠が本当に問いに答えているか
- **Adversarial**: Phase 1c の反対論はすべて Phase 4 で言及されるか、または明示的に却下根拠があるか

NG が残る限り Phase 4 に進まない。WebFetch 予算なし → 解決するまで戻る。

**例外**: stakes=high の claim を 3 source で裏取りできない場合、強制的に `contested` or `unverified` タグを付けて進む（捏造で埋めない）。

## Phase 4 — 構造化出力

```
## 結論
<本文。各主張に [C1], [C2] 形式の inline citation を必ず付ける>

## Claim Table
| ID | Claim | Stakes | Confidence | Sources |
|----|-------|--------|------------|---------|
| C1 | <atomic claim> | high | confirmed | [URL1 (2026-04, primary), URL2 (2026-03, primary), URL3] |
| C2 | ... | medium | likely | [URL4, URL5] |
| C3 | ... | high | contested | [賛: URL6, 反: URL7] |

## Adversarial Findings
Phase 1c で拾った反対論のうち、本文で却下したものと採用したものをそれぞれ記述。

## Confidence Tier
- confirmed: stakes 通りの独立 source 数を満たし、反対論なし
- likely: stakes 通り satisfied だが弱い反対論あり
- contested: 賛否両方の primary source が存在、結論保留
- single-source: 必要 source 数に達していない
- unverified: primary source が取れなかった
```

## 失敗時

不明 / 取得失敗を**捏造で埋めない**。

- WebSearch 0 件: 「検索結果が得られなかった」と明示
- WebFetch エラー 3 回連続: 当該ソースは snippet で代替
- Phase 2 で用語が依然不明: 「未解決」と明記
- claim が裏取れない: `unverified` タグで明記、削除しない

## 打ち止め

- 全 atomic claim が stakes 通りの supporting source を獲得、または
- Phase 3.5 ゲートを通過、または
- 残った claim に `contested` / `single-source` / `unverified` タグが明示済み

## 再現性ログ（必須）

セッション完了時に以下を `~/.claude/plans/deep-run-<short-slug>.md` に自動保存:

```markdown
# deep-strict run <YYYY-MM-DD>

## Topic
<元のトピック>

## Phases
- Phase 1a queries: [...]
- Phase 1c (fact-checker) queries: [...]
- Phase 2 unknown terms resolved: [...]
- Phase 3 fetched URLs: [URL, primary/secondary, date]

## Claim Table
<Phase 4 と同じ表>

## Decisions
- 採用: なぜ
- 却下: なぜ
- contested: なぜ未確定
```

後日 deep-strict の結論を検証 / 反証 / 再走するときの参照源。
