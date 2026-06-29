# factcheck _dev — decisions

Append-only ADR ledger for the factcheck skill and its `template/`. Why a choice was made and what happened. Never rewrite past entries.

## 2026-06-27 — skill 誕生: review-server の example を昇格（Deferred の override）

経緯: review-server に「ブラインド(ファクトチェッカー)GT作成面を別成果物に分離してよい」という方法論は既にあった(review-server decisions 2026-06-24 / judge-loop 横断.md 同日)。だが別skill/別サーバを今 立てるのは G7 premature として不採用＝judge-loop TODO Deferred(トリガ=外部FC実投入)。本セッションでは Deferred を守りつつ形を具体化するため、review-server/examples/fc-handover に動く参考例を作り、オーナー反応で何周も結晶化させた: 中間ページ撤去(commit→次へ直行)・export をレビュアー面から外しオペレータCLIへ・一覧に自分の判定+理由+進捗・確定済み再訪で前回判定プリフィル+改訂・2軸目(根拠の質=デモ用)削除・判定を○/△/×の3値・○○二重丸を消すチップUI。

決定(オーナー裁定): 例を独立 skill `factcheck` に昇格。根拠=オーナー「独立skillの方が skill として sharp ＋ より汎用になる」。これは Deferred の明示的 override。当初 Deferred の根拠(G7 premature)は弱まっている: 形は本セッションで実質 settle した(上記の周回)。トリガ(外部FC実投入)未点灯のまま昇格するが、理由を「campaign痛の反復」でなく「形の結晶化＋skill設計上の鋭さ」に置き換えた裁定として記録。

形(F2 を踏まないための制約): factcheck は gate を再所有しない。S2(単一契約ソース)/S6(tier)/S9(戻し1経路)は review-server 所有のまま compose する(judge-loop が review-server を compose するのと同じ関係)。さもないと「契約を複写するな(F2)」を自分で破る。factcheck が所有するのは ブラインド引き渡し固有の規律のみ: 不在による防火壁・独立判定(賛否トグルにしない/S11)・レビュアー最小面・1コマンド配布+doctor。examples/fc-handover をそのまま template/ に収容(作り直さない)。

汎用性の扱い: 「より汎用」は設計目標であって現時点の主張にしない(G9 over-claim回避)。template は config-driven で judge-loop P2 からも単独からも呼べる形に開くが、実第二caller が現れるまで汎用は断定しない。

未 settle ゆえ焼き込まないもの(grill hook として deferred): 語彙/cardinality(例は○/△/×・意味は per-case)・auth/レビュアー帰属(default none)・campaign別GTプロトコル・複数レビュアー集約。

波及配線: review-server SKILL.md(description/S1/S3/CHOICES/Composition から「別成果物」二役を factcheck へ委譲)・judge-loop SKILL.md(P2/Composition で factcheck を名指し)・judge-loop TODO の当該 Deferred を除去し decisions へ。

検証: 移設後 template/selftest.py PASS(build→S2生成→S3不在→commit/export→S9往復で review-server store へ取り込み blind→gold 昇格可)。判定の中身・コードは移設のみで無改変、selftest のパスのみ review-server/template 参照に更新(不在時 SKIP)。
