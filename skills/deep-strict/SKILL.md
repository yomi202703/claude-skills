---
name: deep-strict
description: 結論を後で再現・検証する必要がある重い web 調査。atomic claim 単位で独立 source 数を満たすまで裏取り (WebFetch 上限なし)、fact-checker による反対論サーチ、PROMOTE/HOLD/contested の confidence tier 付き構造化出力。run が成果物を動かす判断を生んだ時だけ消費側リポの decisions に結論を残す(常時ログは取らない)。技術選定・セキュリティ判断・論文ベースの設計決定など、後日「なぜこう判断したか」を辿る必要がある時に呼ぶ。
---

# deep-strict

固定パイプライン: **Phase 1a → 1b → 1c → 2 → 3 → 3.5 → 4**。

WebFetch は claim 駆動（上限なし）。WebSearch も新規 URL 率 < 30% になるまで自由。判断は捏造で埋めず、`contested` / `single-source` / `unverified` タグで明示する。

## 学術トピック判定（OpenAlex 起動条件）

論文・研究ベースのトピック（手法 / ベンチ / 理論 / サーベイ等、査読・arxiv が一次ソースになる種類）でのみ、Phase 1a・3 で OpenAlex (`api.openalex.org`) を WebFetch で叩く。技術選定・製品比較など査読文献が一次にならない種類では起動しない。迷ったら起動しない。

素の HTTP GET で JSON が返るので新規ツール不要。全 URL に `&mailto=yo.mi202703@gmail.com`（polite pool）を付ける。

**但し書き（実走確認 2026-06）**: 発表 1〜4 ヶ月の preprint は OpenAlex 未索引・低適合で空振りする（cited_by=0 ばかり）。直近 preprint 中心のトピックでは WebSearch/arxiv を主、OpenAlex は補助に留める。citation graph が効くのは索引済みの枯れた文献のみ。

## Phase 1a — 並列メタスイープ

Agent ツールで Explore 型 subagent を複数本並列起動。各 subagent への prompt:

```
WebSearchして「{クエリ}」。URL / title / 1行 snippet の表だけ返す。
```

### Step 0 — 語彙ブートストラップ（ジャーゴン既知ならスキップ）

精密クエリは「正しい術語を知っている」前提に立つ。知らなければ初手が外れ精度が運任せになる。先に広域検索を 1 本撃ち、術語を拾ってから本スイープを組む:

```
WebSearchして「{トピックの素朴な言い換え}」。URL / title だけ 15-20 件返す。
```

戻ったタイトルから分野の用語（手法名・略語・タスク名・ベンチ名）を抽出し、以降のクエリに使う。

### Step 1 — 精密スイープ（並列）

クエリ設計:
- **2 軸に割る（年トークンで標準解を隠さないため）**:
  - 鮮度軸（日付つき, literal 2026-MM。"X 2026年5月" / "X May 2026"）: 最新を狙う。
  - canonical 軸（日付なし, "X method" / "X survey" / "X baseline"）: 基礎・標準・既存ベースラインを狙う。手法列挙や標準/古典を含む問いでは答えの一部が 2026 以前にあるため必須。
- 各軸で視点を変える: "X vs alternatives" / "X benchmark"（視点違い）、"X failure" / "X limitations" / "X 批判"（否定・限界）。
- **言語ゲート**:
  - 論文・研究ベース（OpenAlex 判定と同じ）: 英語一択。JP は撃たない（一般記事ノイズになるだけ）。
  - 日本固有（国内制度・事情・邦文一次資料）: JP をフル軸で必須。
  - どちらでもない（海外発だが国内議論もある等）: 英語フル + JP 確認 1 本。

subagent 戻り値を本体 context に集約。

**学術トピックなら追加軸（OpenAlex 発見）**: 次の WebFetch を 1〜2 本足す。日付フィルタで時間アンカーが正確に効く。
```
https://api.openalex.org/works?search={topic}&filter=from_publication_date:2026-01-01&sort=publication_date:desc&per_page=10&mailto=yo.mi202703@gmail.com
```
戻り値から `title` / `id` / `doi` / `publication_date` / `cited_by_count` を拾い、他の検索結果と同じバッファに入れる。

**Checkpoint**: 鮮度・canonical 両軸を撃ったか／収穫した用語で組んだか／言語配分は適切か（論文なのに JP を撃っていないか・日本固有なのに英語偏り）を自問し、欠けがあれば 1 度だけ追補。

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

WebSearch を以下のクエリで実施（言語は Phase 1a の言語ゲートに従う＝論文・研究ベースは英語一択、日本固有は JP、grey は両方。YYYY-MM は literal 2026-MM、現在月で展開）:
- "{topic} criticism 2026-MM"
- "{topic} limitations 2026-MM"
- "{topic} failed cases 2026-MM"
- "{topic} alternative beats 2026-MM"
- （日本固有 / grey のみ）「{topic} 批判 2026年MM月」「{topic} 限界 2026年MM月」

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

未知語解決は定義取得が目的なので、**canonical 軸（日付なし）を既定**にする（1a の鮮度軸と逆）。新語で定義が出ないときだけ literal 2026-MM を付けて鮮度軸へ。

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

**学術なら独立性補強（OpenAlex 被引用）**: high/medium の論文 claim は OpenAlex で当該 work を引き、citing works を独立 source 候補にする。
```
https://api.openalex.org/works?filter=doi:{doi}&mailto=yo.mi202703@gmail.com   # cited_by_count / cited_by_api_url
{cited_by_api_url}&per_page=5&mailto=yo.mi202703@gmail.com                       # citing works
```
著者・組織が異なる citing works のみ独立に数える（自己引用は除外＝Phase 3 Step 1 の独立定義）。

**ガード**: 被引用数は人気であって正しさではない。これで Phase 1c の反対論を却下しない。独立 source の有無の補強のみに使い、真偽判定には使わない。

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

## Retry Queue（取得できれば結論を上げられる未取得物）
| 対象 (URL / 検索語) | 失敗理由 | 取れると何が上がるか |
|---|---|---|
| <URL or 検索ターゲット> | fetch×3 / redirect / paywall・login / 検索0件 / primary 不在 | <例: C3 single-source→confirmed / 未読 anchor> |
```

`single-source` / `unverified` / `contested` の claim は「何を取れば解消するか」を 1 行ずつ Retry Queue に残す（空なら「なし」）。

## 失敗時

不明 / 取得失敗を**捏造で埋めない**。

- WebSearch 0 件: 「検索結果が得られなかった」と明示
- WebFetch エラー 3 回連続: 当該ソースは snippet で代替
- Phase 2 で用語が依然不明: 「未解決」と明記
- claim が裏取れない: `unverified` タグで明記、削除しない
- 上記の各取得失敗は Retry Queue（Phase 4）に 1 行記録する — 後で手動取得 / 再走する用

## 打ち止め

- 全 atomic claim が stakes 通りの supporting source を獲得、または
- Phase 3.5 ゲートを通過、または
- 残った claim に `contested` / `single-source` / `unverified` タグが明示済み

## 結論の記録（run が判断を生んだ時だけ）

常時ログは取らない（`~/.claude/plans/` への自動保存は廃止）。理由: ephemeral fact の run はログが鮮度で腐り、検証時も結局その場で検索し直すので「参照源」として働かない。価値が出るのは結論が durable な成果物（スキル / 設計 / 技術選定）を動かした時だけで、それは本来 decisions（なぜその選択をしたか＋何が起きたか）に属する。

判定: この run の結論が成果物を変える/作る判断を生んだか。

- 生んでいない（純粋な事実確認・調べ物で終わる）→ 何も残さない。Phase 4 の構造化出力を会話で返して終了。
- 生んだ → その判断を消費する側のリポの decisions ledger に 1 エントリ追記する:
  ```markdown
  ## <YYYY-MM-DD> <一行の結論>
  - 根拠: 効いた claim と confidence（例 C2 confirmed: vLLM #40080 解決）
  - 影響: どの成果物の何が変わるか
  - 残り: contested / unverified が残るなら何を取れば解消するか（なければ省略）
  ```
  消費側に decisions が無ければ最小の append-only ledger（`_dev/decisions.md`）を1つ作って入れる。Phase 4 の Claim Table / Retry Queue 全文は会話側に出すだけで、decisions には結論と効いた claim だけを落とす（生ログを移植しない）。
