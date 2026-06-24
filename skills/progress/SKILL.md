---
name: progress
description: リポの進捗を governance ドキュメント(STATUS / TODO / decisions / README)から決まった順で読み、短い oriented report を出す。加えてドキュメント間の食い違い・governance ルール違反(完了が TODO に残存・Deferred にトリガ無し・STATUS↔TODO の矛盾)を flag する。読むだけで書き換えない。ユーザーの「今の進捗は？」等の質問で起動
---

# progress

working docs から「今どこ・次に何を・なぜそうなったか」を読み取って短く報告し、doc 間の食い違いを点検する。読むだけ(STATUS/TODO/decisions を書き換えない。修正は user 依頼か doc 系 skill に委ねる)。自分で読む(サブエージェントに投げない。数ファイルの末尾だけなので軽い)。

役割定義(TODO/STATUS/decisions/archive)は global CLAUDE.md に従う。

## 1. 探して読む

リポ内で STATUS / TODO / decisions(配下の .md 群か単体。トピック分割あり) / README を探す(`成果物/` `docs/` ルート直下を当たる)。見つからない役割は report 冒頭で「無し」と書く(欠落も情報)。一つも無ければ `/claude-md` を案内して終了。

順に: STATUS(今どこ)→ TODO(次の一手とブロック)→ decisions の末尾だけ(直近の why。末尾 3〜6 エントリ、または STATUS が参照する日付まで。分割時は更新が新しいファイル)→ README(あれば前提と正本の所在)。

## 2. 食い違いを点検(付加価値)

読んだ内容を以下に照らす。確信できるものだけ挙げ、割れるものは「要確認」と弱く出す。該当無しなら「異常なし」一行。

- 完了の残存: 「完了/確定/done」とされた項目が TODO の Active に残っていないか。
- トリガ無し Deferred: Deferred 各項目が解除トリガを名指しているか。無ければ Active か won't-do のどちらか=違反。
- STATUS↔TODO の矛盾: STATUS の「次の一手」と TODO の P0 が食い違っていないか。
- 鮮度: STATUS が decisions 末尾の日付より古いままになっていないか。
- 理由の抱え込み: TODO 項目が理由を本文に持っていないか(理由は decisions に置き日付で参照する)。