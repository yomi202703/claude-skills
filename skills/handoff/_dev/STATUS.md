# handoff — STATUS

_(旧名 task-handoff。2026-06-30 改名 ── decisions 参照)_

_現状スナップショット。セッションごとに書き直す。短く保つ。_

## 何のskillか
- 作業ストリームを、別の full-fidelity main セッションがファイルから cold で引き継げる形で渡す。main 同士はファイルで通信する(subagent の lossy 要約ではない)。
- 存在理由は1点: 分岐点の load-bearing 文脈は会話の中にしか無く、ファイルに指す先が無い。だから著述するしかない ── それが foundation.md。
- skill は2手順だけ: (1) foundation.md を著述(あるものは指す/会話にしか無いものだけ書く)、(2) 発行者の TODO に Deferred join 行を残す(ALL-of-set トリガ/ストリーム dir を指す/発火=validity 判断)。

## ドキュメント層の役割分担
- `SKILL.md` … 配布される本体。2手順 + 委譲 + 再肥大ガード。
- `_dev/` … このskill自体の開発ワークエリア(四役ガバナンス)。
  - `decisions.md` … skill の形の meta-ADR。dispatch 実装の一次台帳は plugin リポ(`~/Projects/tabby-claude-status/decisions.md`)。

## いまの状態
- 2026-06-30 grill-me(冷モード)で過剰機能を削除し、2手順形に書き直し済み。切ったもの: PM という場所・registry シート・shared schema/integration target/version stamp のフィールド化・grill-me 必須前提・judge-loop sub-skill 枠。詳細は decisions 2026-06-30。
- 再合流は発行者 TODO の Deferred join 行に一本化(別 registry も維持 PM セッションも無し)。registry は広い fan-out のときだけのオプション索引に降格。
- dispatch(任意の eager-launch 層)は無傷で存置。初期プロンプトに焼くのは TASK.md → foundation.md に更新。設計は decisions 2026-06-27。
- judge-loop ルーティング節の削除(旧 in-flight 編集)は書き直しに吸収済み。

## このセッション(2026-06-30)
- /grill-me を冷モードで回し、behavior-delta ゲートで skill の存在理由を1点(foundation 著述)に絞った。
- SKILL.md を2手順形に全面書き直し、decisions に確定エントリを追記、STATUS/TODO を更新。
