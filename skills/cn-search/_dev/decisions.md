# cn-search decisions

Append-only ADR. Why a choice was made and what happened.

## 2026-06-27 cn-search を新設し、CN 取得知識を単一所有させる

deep-strict と zeitgeist が CN 一次ソースの取得知識（火元カタログ・壁越え到達・ZHクエリ作法・CNトピック判定・pick-best/ランキングガード）を二重に抱えていた。単一所有者として cn-search に切り出し、親2つはインライン記述を参照へ張り替えて短縮（deep-strict −12行・zeitgeist −6行）。

抽出境界：cn-search はソース/到達/ZHクエリ/pick-best を所有する。読み込み・corroboration・複数の目は所有しない——deep-strict 固有の epistemics（ZH独立性カウント・Phase3.5 ZH一次ゲート）と zeitgeist 固有の velocity 計算式・レンズは親に残した。

## 2026-06-27 単独完結スキルとして書く（compose は従）

初版は「呼び出し側に供給するだけ・読み込みはしない」と従属コンポーネント的に書いてしまい、取得スキルなのに単独起動が見えなかった。単独起動が本筋（CN一次判定→ZHクエリ→壁越え→カタログから引く→取得素材を火元別に返す）、deep-strict/zeitgeist がその取得層を借りる側、と主従を反転。「やらない（読み込み・裏取り・複数の目）」は単一責任の境界として残す。

## 2026-06-27 到達は API ファースト

初版は到達順が WebSearch 先頭で、直 WebFetch を fallback に落としていた。API/RSS を持つ火元（V2EX・Bilibili・36氪/少数派/IT之家 の feed・GitHub Discussions）は直叩きが最良経路（本物の per-item タイムスタンプ）。優先順を API > WebSearch > Gemini 橋 > 直ページ に並べ替え、body に原則・reference/sources.md に実エンドポイントを置く分担。

## 2026-06-27 カタログは実測で確定

到達ステータス（proven/probe）は捏造で埋めず実測。proven は WebFetch（Claude 側＝US インフラ）の vantage で取れたもの。velocity 計算可＝V2EX・Bilibili・36氪/少数派/IT之家 RSS・GitHub Discussions。掘金は POST ルートで probe。微博は visitor passport へ 302（認証壁）でランキング媒体（発見補助）へ降格。注意：ローカル Mac（日本）からの到達は vantage が違い未実測。

## 2026-06-27 種出しは qwen-web、glm-web は使わない

定番外の CN 辺境ソースは CN ネイティブモデルに吐かせて catalog を広げる（→機械到達するものは実測昇格、参加制は人手枠へ）。種出しの実行役は qwen-web。glm-web は CN 固有語を西側的に再構成して外すため CN ネイティブ知識には使わない（glm-web decisions 参照）。

## 2026-06-27 fetch スクリプトは defer

「API 火元を束ねて取得＋検索」は WebFetch（取得＋prompt で絞り込み）で既に成立。スクリプト化はメンテ（CN API ルートのドリフト）を生む。再開トリガ：cn-search を CN 版 zeitgeist 的に繰り返し回すと決めたら、ローカル到達プローブ→薄い fetch スクリプト（catalog の API 火元を並列取得→正規化→velocity ソート）の順で着手。
