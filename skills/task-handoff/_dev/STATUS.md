# task-handoff — STATUS

_現状スナップショット。セッションごとに書き直す。短く保つ。_

## 何のスキルか
- 分岐点で自己完結のタスク契約を発行し、別の full-fidelity main セッションがゼロ context loss で独立ストリームを引き継げるようにする。main 同士はファイルで通信する(subagent の lossy 要約ではない)。
- 所有するのは3つだけ: 分岐点の handoff contract / 1タスク1ディレクトリの micro-dir 形 / 発行済みタスクの registry。判定ロジックは持たない(judge-loop からルートされる側)。

## ドキュメント層の役割分担
- `SKILL.md` … 配布される本体。ファイル契約の作法。
- `_dev/` … このスキル自体の開発ワークエリア(四役ガバナンス)。
  - `decisions.md` … スキルの形の meta-ADR。dispatch 実装の一次台帳は plugin リポ(`~/Projects/tabby-claude-status/decisions.md`)。

## いまの状態
- 本体はファイル契約のみ(foundation/TASK + 四役 docs/registry)。これが正本。
- micro-dir の working docs は global 四役の正式名に統一済み(decisions.md / STATUS.md / TODO.md ── 旧 `decision.md`/`todo.md` のリネーム・STATUS 欠落を 2026-06-30 修正)。throughline との境界(機械向け契約 vs 人が読む派生ビュー)も SKILL に明文化。
- dispatch(任意の eager-launch 層)プロトタイプが本日着地: Tabby プラグイン tabby-claude-status 改修で「task dir の TASK.md を初期プロンプトに argv ベイクして独立タブで claude 起動」が成立。設計は decisions 2026-06-27 参照(A=独立タブ/argv ベイク/ephemeral 非永続/sendInput は追い投げ専用)。
- in-flight: SKILL.md に別件の未コミット編集(judge-loop ルーティング節の削除)あり。dispatch は SKILL.md 未記載。

## このセッション(2026-06-27)
- Tabby 実機を調査(profile=launch spec / sendInput 実証 / CDP は stale)し、dispatch を設計・実装・検証・live インストール(可逆)。
- _dev/ を新設し dispatch 設計を decisions に接地。
