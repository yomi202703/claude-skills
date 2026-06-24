# gemma-prompt decisions

append-only ADR。なぜその選択をしたか＋何が起きたか。過去エントリは書き換えない。

## 2026-06-24 文法強制=無限ループ前提(SKILL 行7)に「vLLM では緩和」の但し書きを付ける
- 根拠: deep-strict 検証 run(gemma4-31b-properties ログの再走)。C2 confirmed — vLLM issue #40080 が Closed（修正PR #40097/#40099、grammar 制約 decoding 時に RepetitionDetectionParams を自動有効化）。primary は GitHub issue で Closed を直接確認。
- 影響: SKILL 行7「文法強制をかけると EOS を塞いで無限ループ化する」は vLLM では緩和済み（自動 repetition detection で loop 回避可）。よって constrained decoding 回避を全ランタイム一律の前提にはできない。
- 判断: 防御的設計（prompt 依頼 JSON＋空許容＋evidence 必須）は default のまま維持する。理由＝fix は vLLM 限定で、llama.cpp #21375 / ollama #15502 / gemma 本体 #610,#622 は関連ループが root cause 追跡中＝モデルレベルの繰り返し癖は残存。スタンスは「vLLM なら緩和、他ランタイムでは依然有効」へ更新。
- 残り: 修正の正確な日付は unverified（検証 subagent は「2025-11」と返したが、本スキル土台ログが 2026-06-13 に「未解決」と記録した事実と矛盾し primary に日付なし。Closed という状態のみ確定）。
- 適用: 但し書きは SKILL 行7 に反映済み。

## 2026-06-24 旧 deep-strict ログ(6/13–6/20)の結論を集約（plans/ 廃止に伴う吸い上げ）
SKILL 本体の「前提」「7か条」の出所。生の Claim Table は移植せず結論と効いた claim のみ。

- 過信・埋め癖の主因は RLHF/アライメントでサイズ非依存（gemma-overconfidence, C3 likely / C4 contested）。当初の「中型=構造的に断言（サイズ法則）」は下方修正済み。Gemma 系の較正の弱さ自体は single-source(C5)で確証は弱い。→ 前提「過信・埋め癖」の根拠。事実は入力で渡す設計はここから。
- 出力遅延/ハングの主因は grammar/JSON 制約下の繰り返しループ（max_tokens まで生成）＝vLLM #40080、加えて 31B Dense+FlashAttention の長プロンプトハング・長ctx の KV cache 圧迫・VRAM 枯渇 swap（gemma4-slow-output, C1/C2/C4/C5 confirmed）。loop は速度問題でもある。#40080 のその後は上の 2026-06-24 エントリ参照。
- プロンプト長は「20–30行が常に最適」ではない。効くのは長さでなく(具体性 × 同時判定数)。1コールの同時判定数が増えると指数崩壊（prompt-length, C1 confirmed=IFScale 2507.11538）。→ 7か条 #1「短く具体的」#2「10カテゴリ以内」の根拠は“行数”でなく“同時決定数”。
- Gemma 4 は native system role 対応、公式 chat template/control token を使う（open-model-prompting, C1/C2 confirmed）。プロンプトはモデル間で転移しにくい(>30%劣化, C3 confirmed)＝「最強モデルのプロンプト流用禁止」の根拠。31B は指示追従が強く過剰な few-shot CoT は無益(C4 contested)＝サイズで扱いを分ける。
