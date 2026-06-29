# task-handoff decisions

append-only の ADR 台帳。task-handoff スキル「そのものの形」についての判断を残す(なぜファイル契約か・dispatch をどう位置づけるか・構造変更の why)。新しいエントリは末尾に追記する。過去エントリは書き換えない。

スコープの線引き: ここはスキルの形の meta-ADR。dispatch を実装する Tabby プラグインの実装判断(関数シグネチャ・ビルド・配線)は `~/Projects/tabby-claude-status/decisions.md`(プラグインリポ側の台帳)が一次。複写せず参照する。SKILL.md は一枚ゆえ当面この単一ファイルで足りる(肥大したらトピック分割)。

## 2026-06-27 — _dev/ 開発ガバナンス層を新設
- 決定: task-handoff に `_dev/`(decisions / STATUS / TODO、必要時 archive)を新設。global CLAUDE.md の四役ガバナンス準拠。兄弟スキル(judge-loop ほか)の慣習に合わせフォルダ名は `_dev/`。
- 理由: これまで実体は SKILL.md 一枚で、「なぜこの形にしたか」を残す台帳が無かった。dispatch 設計(下記)を機に、判断を接地して回せる場を起こす。
- 起点状態: SKILL.md はファイル契約のみ(foundation/TASK/decision/registry)。dispatch は本日プロトタイプが着地した追加層(下記エントリ)。

## 2026-06-27 — dispatch を「ファイル契約の上に乗る任意の eager-launch 層」と位置づける
- 発端(オーナーの興味): /atlas や /chatgpt-web のように、別 main セッションを Tabby の新規タブとして自動で起こし、そこへプロンプトを直接入れられないか。/claude-desktop でも代替できるが機構として素直か検証したい。
- 確定した位置づけ: dispatch は SKILL.md のファイル契約を置き換えない。契約ファイル群(foundation/TASK/decision/registry)が依然として正本で、cold 再起動可・1週間単独走行可・人間駆動の再合流という不変は無傷。dispatch は「いま並列で走らせたい」regime を加速するための任意の起動層であって、「数週間後に cold 再開」regime を捨てない。両 regime は description が既に両方挙げている。
- 機構の核(なぜ atlas 系の真似ではない): atlas/chatgpt-web/claude-desktop は相手が GUI で正規のプロンプト入口が無いから画面を puppet する。task-handoff が起こしたい別 main は Claude Code = CLI で、argv/stdin という正規入口がある。ゆえに「タブにキーストロークを流し込む」(fragile)ではなく、プロンプトをプロセス起動引数に焼く(robust)を採る。Tabby の役割は配送ではなく「可視化と人間の引き取り」(可視タブで監督・途中介入できる)。
- Tabby 側の前提(実機調査で判明): ユーザーの「workspace」は Tabby ネイティブ概念でなく、config.yaml に手で組んだ規約 = `group: workspaces` 下の local profile 群で、各 profile が「ある cwd に cd して claude を起動」する launch spec。これは本スキルの「PM は場所(ディレクトリ)」のターミナル上の実体化。プロンプト投入 API も既存自作プラグイン tabby-claude-status が sendInput で実証済み。ゆえに外部 CDP も System Events も不要、in-process プラグインの DI だけで完結する。

## 2026-06-27 — dispatch 設計の4つの確定判断
- A: 独立タスクは独立タブ(同じ workspace に同居させない)。オーナー裁定。
  - 却下した B: 親の split にペインとして同居(addClaudePane 方式)。理由: 親 main の画面に間借りさせると「別 main・cold 再起動可・単独走行」という独立性とぶつかる。独立ストリーム = 独立タブが既定として自然。
  - 留保: 「分岐元の隣に並べて一望したい」運用は B 系。その時は fan-out(buildGrid で兄弟を split に並べる、recall の3面方式)として別途足す。TODO Deferred。
- argv ベイク(初回プロンプト): `claude --permission-mode auto "$(cat '<TASK.md>')"`。本文を inline quote せずファイル経由にするのは、多行・日本語・埋め込み `"` `'` `$` バッククォートでクォートが壊れないため。コマンド置換の出力は再パースされず、全文が単一 argv として届く(実 zsh 経路で argv 観測し検証済み・`$HOME` もリテラル保持)。プロセス起動時点でプロンプトが渡るのでレース無し。
- sendInput は追い投げ専用: 既存タブ/走行中セッションへの追加指示用。初回プロンプトには使わない(claude TUI が ready になる前に送ると取りこぼすタイミング依存があるため、初回は argv ベイク一択)。
- ephemeral(config 非永続): dispatch は profile を config.yaml に保存せず `openNewTabForProfile` で即オープン。プロンプトを焼いた profile を永続化すると毎回プロンプトが再実行され config が汚れる。あわせて group は `workspaces` でなく `tasks`(独立タスクは workspaces グループの一員でない)。
- /claude-desktop との関係: 本 dispatch はその CLI 版アナログ。claude-desktop は GUI を Accessibility で puppet(配送が脆い側)、本 dispatch は argv 配送で堅く、相手が CLI ゆえログ/再開/scriptability が素直。

## 2026-06-27 — 着地と未反映
- 着地: tabby-claude-status を改修(buildWorkspaceProfile に promptFile 引数 + dispatch ボタン)。ビルド・live インストール済み(純正バックアップ index.js.bak-prebake 保持・可逆)。Tabby は起動時ロードゆえ反映には再起動が要る = 走行中 claude を巻き込むため自動再起動はせず、検証はオーナーのタイミングに委ねた。デモ task dir `~/Projects/_dispatch-demo/TASK.md` を用意。
- 未反映(意図的): SKILL.md には dispatch を未記載。理由: SKILL.md に別件の未コミット編集(judge-loop ルーティング節の削除)が乗っており、契約本体への追記を絡めない。dispatch を SKILL.md へ薄く一行差す(任意の eager-launch 層として)のは TODO Active、オーナー確認の上で。

## 2026-06-30 — micro-dir の四役名を global に揃え STATUS を追加(不整合の修正)
- 発端: オーナー指摘「task-handoff が global CLAUDE.md と不整合」。
- 不整合の実体: 「Delegates」節は四役(TODO / STATUS / decisions / archive)を「reuse, never redefine」と宣言しているのに、micro-dir shape が黙ってリネーム = `decision.md`(単数・global は `decisions`)/ `todo.md`(小文字・global は `TODO`)、かつ `STATUS` を丸ごと欠落。本スキル自身の `_dev/` は正しく `decisions.md / STATUS.md / TODO.md` を使っており、本体が自分の dogfood と矛盾していた。
- 修正: micro-dir の working docs を四役の正式名(decisions.md / STATUS.md / TODO.md)に統一。定義は再掲せず role 名で global を指す(「reuse, never redefine」の実践)。STATUS.md を任意項目として追加 ── long-running stream の cold 再起動が「いま実行のどこか」を読む唯一のスナップショットで、本スキルが防ぎたい失敗(mid-flight で再開不能)に直結するため、todo より本質的。
- throughline との境界も明文化: タスク dir のファイルは cold main が実行する機械向け正本、人が読む振り返りビューは throughline の出力(view≠真実)で view 層(`.lavish/` 既定、repo-shape が予約)に置き契約には複製しない。throughline 側は出力先を `成果物/handoffs/` から外す対応(throughline _dev 参照)。
- ripple-check(2026-06-30 同日): 上記 SKILL の境界文に「macro 層に置く」と書いたが throughline の正本置き場は `.lavish/`(repo-shape:33)で 成果物/ は fallback。不正確ゆえ SKILL から位置主張を削除(本文は「複製しない」が要点)。throughline:53 の「スロットは repo-shape が macro 層に定める」も overclaim(repo-shape は `.lavish/`/`narrative/` を予約・`成果物/views/` は予約スロットでない)につき削除、委譲は既存の末尾行に集約。
