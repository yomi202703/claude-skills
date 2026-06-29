# chatgpt-web _dev / decisions（append-only）

過去エントリは書き換えない。

## 2026-06-27 摩擦記録：前置き(思考)中に前置きを完了と誤認して早期return

事象（skill-gripe、実使用中に観測）
- 複雑なタスク（温泉候補の表生成）を投げたとき、ask.py が ChatGPT の「前置き(思考中)」テキストだけを返し、本来の最終回答（表）を返さなかった。再送しても同じく前置きだけ。最終的に cdp.py で最後の assistant turn を直読みして本回答を回収した。
- ユーザー指摘：ChatGPT は必ず前置きを出す仕様で、複雑なタスクほど思考フェーズが長い。その完了前にこちら(Claude)が催促するので噛み合わない。

根本原因（特定済み、ask.py:78-81）
- 完了判定にエスケープ節 `(gen and stable >= 8)` がある。意図は「生成終了後に stop-button が stuck で残る」ケースの救済（ask.py:58-60 のコメント）。
- だが ChatGPT 推論モデルの挙動は「前置きを出す → gen(stop-button=生成中)を true のまま長く思考 → 本回答をstream」。思考中は前置きテキストが変化せず stable、gen も true のまま。
- poll は sleep 2s。前置きが約16秒（stable≥8 × 2s）変わらないと、生成がまだ続いているのに `gen and stable>=8` が発火し、前置きだけで return する。これが早期return＝噛み合いの原因。
- 補助：stall recovery（ask.py:84-91）は「text が空のまま gen」した時だけ働く。前置きが既に表示されている場合は空でないので発火せず、救済にならない。

回避策（現状の運用）
- 前置きだけ返ってきたら催促せず、cdp.py で最後の assistant turn を直読みする（SKILL の onsen 側にも明記済み）。

改善案（未適用・要オーナー判断）
- 案A：gen==true の間は stability で settle しない（gen が false に落ちて初めて確定）。stuck stop-button のhangは stall/timeout 経路に寄せる。最も正しいが stuck 救済を弱める。
- 案B：`gen and stable>=N` の N を大幅に上げる（例 stable>=30 ≒60s）。思考ポーズ(通常<60s)では発火させず、本当にstuckなものだけ拾う。実装は1行で軽い。
- 案C：推論UIの「思考中」要素を検出し、それが消えるまで return しない（セレクタ追従コストあり）。
- 注意：robustness 設計は gemini-web と共有。変更時は gemini-web 側 ask.py のミラー要否を確認する。

## 2026-06-27 修正適用：案A（生成中はstabilityでsettleしない）

- 採用＝案A。`(gen and stable>=8)` の早期return節を削除。新ロジック（ask.py poll_reply）：
  - `not gen and stable>=3` の時だけ確定（生成が本当に終わった時）。
  - `gen and stable>=20`（≒40s 同一テキストで生成継続中＝思考/前置きポーズ or stuck stop-button）なら settle せず reload_recover して再読み・継続。
- 根拠：早期return（回答丸ごと取りこぼし）は stuck stop-button（timeout経路の reload+直読みで結局回収できる）より重い失敗。正しさを優先し、stuck は ~40s 周期の reload に寄せて時短も両立。
- gemini-web/scripts/ask.py も同一修正でミラー（robustness設計共有のため。ユーザー承認済み）。両ファイル py_compile OK。
- 未実機検証（Chrome/sign-in 要）。次回 chatgpt-web 実使用時に、複雑タスクで前置きでなく本回答が返るか確認する。

## 2026-06-27 追加：nav.py（リポ探索つきChatGPT相談）

- scripts/nav.py を新設。ChatGPTにツリー＋fetchプロトコルを渡し、要求されたREAD/GREP/LS/TREEをread-onlyで自動充足してディレクトリ探索を疑似再現する。cdp.py/ask.py を再利用。
- サブコマンド: consult（自律1ショット＝brief投入→fetch自動応答→最終回答をstdout）／seed／serve（人間主導でタブ監視・自動応答）／brief。
- 実証: nav-demoのクロスファイルbug（discount.pyのpercent未換算）を、ツリーのみ提示→ChatGPTがfetch→自動応答→正しいdiff、で特定。さらに pi(Gemma) が `nav.py consult` を自分で叩き、diff適用→`python3 src/main.py`→768.0 まで自律完走。SKILL.md に「Repo-aware consult」節を追記済み。
- 設計判断: 編集はnav側でやらない（read-only）。適用＋テストは呼び出し側（pi/Gemma等）。安全＝リポ直下スコープ＋実在チェック＋ファイル/返信サイズ上限。遅延が実課題で、ChatGPT側の速いモデルが効く。実装中の発見: コードブロックは textContent だと改行が潰れる→innerText で取得。serveにも ask.py の reload_recover を組込み（推論モデルの空ストール対策）。
- 保留（要オーナー判断）: サブコマンド名 `consult` が既存スキル `consultant` と概念的に紛らわしい。改名候補 ask-repo / explore / review。既定案は ask-repo。TODO参照。
