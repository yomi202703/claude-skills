# factcheck の template: ファクトチェッカー引き渡しパッケージ（分離成果物型）

factcheck スキルの runnable template。review-server の CHOICES「GT作成面 = 開発サーバのモード or
別の引き渡し成果物」のうち 後者（別成果物）を所有する。ホストはこれを起点に複製し、`source/` の契約と
ユニットを自分のドメインに差し替えて使う。判定の中身でなく「分離する時の作法」を体現する。

## なぜ2つの形があるか

review-server の `template/server.py`（同居型）と この `fc_server.py`（分離型）は、同じ防火壁(S3)を
別の手段で実現します。

- 同居型: 1サーバが /diag と /review を両方持ち、防火壁は RENDER 時 ──
  /review ハンドラが judges() を呼ばない、という規律で機械出力を隠す。
- 分離型（本例）: 防火壁は 不在 で実現 ── このフォルダには judges() 関数も答えDBも存在しない。
  `source/` は契約とユニット(入力+根拠)だけで機械の答えを持たず、build_package.py はそこから
  input+evidence だけを生成するので、パッケージに機械の答えが入らない（本物のホストでは adapter が
  judges() も持つが、build はそれを一切読まない、が規律）。レビュアーが answer に到達できないのは
  `if` ではなく「そこに無い」から。methodology が S3/S10 で「最強形＝不在による隠蔽」と呼ぶのがこれ。

外部の非技術レビュアーに渡す時はこちらが衛生的（渡すフォルダに開発者用の物が混ざらない）。

## 守っている不変（跨いで効く）

- S2 単一契約ソース: 契約はハンドコピーせず build_package.py が `source/contract.json`
  （この例の単一ソース＝本物のホストでは開発側システムの契約に当たる）から 生成 する
  （`_generated` スタンプに出所＋版を記録）。あかつき最大の失敗(F2)=分離した人間サーバが契約を別に
  焼き直してドリフト、への構造的対策。軸・語彙を変えるのは `source/contract.json` だけ ── radio も
  export も自動で追従する。例の現状＝1軸「判定」の3値 ○/△/×（記号の意味と表現はケースで変える）。
  ソースが動いたら build_package.py を再実行するだけ。
- S9 GT戻し1経路: 判定は commit 時点で内部(fc_gt.db)に自動保存される ── レビュアーが
  「エクスポート」を押す必要はない(その導線はレビュアー面に無い)。GTを集めて開発サーバへ戻すのは
  オペレータ操作 `python3 fc_server.py --export`。吐く CSV は開発サーバ `POST /ingest` が読む列と
  完全一致し、そのまま inbox に置けば同じ取り込み口で戻る。第二の手動取り込み経路は作らない。
- S6 provenance: 本パッケージが生む GT は provenance=blind のみ。gold 化は開発側で
  独立ブラインド再確認の後に行う（blind→gold は dev 側 store.ALLOWED が許す）。ここでは gold を付けない。

## 使い方

    # レビュアー
    python3 build_package.py     # source/ の単一契約ソースから dist/ を生成（答えは入らない）
    python3 fc_server.py         # ブラインド面のみを起動（http://localhost:8040/）
    #   → レビュアーは判定(○/△/×)＋理由を確定するだけ。保存は commit 時点で内部に自動で入る。
    #   → 一覧で自分の判定＋理由＋進捗(N/6)が見える。確定済みを開くと前回判定が初期表示され改訂可。

    # オペレータ（返ってきたパッケージから GT を回収して開発側へ戻す・S9）
    python3 fc_server.py --export inbox.csv   # 保存済みGTを inbox CSV へ
    #   → そのCSVを開発サーバの inbox/ に置き POST /ingest で戻す

    python3 selftest.py          # 上記の主張を端から端まで検証（PASS=GO）

selftest は、契約が生成物であること・パッケージに機械出力が一切無いこと・export 列が
ingest 契約と一致すること・吐いた行が dev 側の同じ Store.append を通って戻り blind→gold
昇格可能であること、までを実際に通して確認します。

## これは Deferred 項目を閉じない

judge-loop TODO の「ファクトチェッカー引き渡し面を別成果物/別スキルとして起こす
［外部FC実投入 & campaign痛の反復 がトリガ］」は据え置きのまま。本例は方法論の
実演であって、実案件向けの本番起こしではありません。
