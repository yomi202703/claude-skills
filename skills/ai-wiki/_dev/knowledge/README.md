# ai-wiki skill-specific knowledge notes

このディレクトリは ai-wiki 固有のリサーチ引用を置く場所 (skill-agnostic なものは `~/.claude/selfimprove/knowledge/` に置く)。

## 既に引き継いでいる研究文脈

### 学習理論
- **Retrieval practice 2025 meta-review**: https://pmc.ncbi.nlm.nih.gov/articles/PMC12292765/ — 採点なし想起の定着効果、SRS starvation の限界
- **mcp-study v2 要件定義書** (自己作成): count-based drill、coverage guarantee、決定的 term extraction の 3 原則

### Knowledge graph / LLM Wiki
- **Karpathy LLM Wiki パターン**: https://a2a-mcp.org/blog/andrej-karpathy-llm-knowledge-bases-obsidian-wiki — 4-stage pipeline, schema emerges, LLM is the maintainer
- **obsidian-wiki (Ar9av)**: https://github.com/Ar9av/obsidian-wiki — multi-agent skill 実装。`/wiki-query` を skill 化しない判断の出典
- **Supercharging LLM Wiki with Knowledge Graphs (Nodus Labs)**: https://support.noduslabs.com/hc/en-us/articles/26724863249180 — graph enhancement + InfraNodus plugin

### Self-improvement loop
- `~/.claude/selfimprove/knowledge/loop_design.md`: Reflexion / Voyager / CRITIC / STOP / Self-Refine の 2023-2026 synthesis
- **CRITIC (Gou 2023)**: external tool-grounded signals が self-correction を成立させる → 我々の hook_check.sh が ground truth
- **Reflexion (Shinn NeurIPS 2023)**: verbal-memory RL、reflections を episodic memory に → CHANGELOG.md + IMPROVE.md の位置付け

## 追加するときの約束

1. 一次情報 (論文 / OSS repo) を優先、二次的 blog は補足
2. 「なぜこの研究が ai-wiki に関係するのか」を 1 行書く
3. 具体的な採用判断 (採った / 却下した / 保留) と紐付けて ALTERNATIVES.md に参照を書く
