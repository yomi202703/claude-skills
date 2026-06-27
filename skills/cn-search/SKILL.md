---
name: cn-search
description: CN 一次ソースの取得スキル。単独で完結して使える——CN の AI/モデル/市場/規制トピックについて「どの中文火元を・どう壁越えして・どんな ZH クエリで」取りに行き、取得素材（火元別のタイトル/要点/リンク）を返す。同時に、この取得知識の単一所有者として deep-strict（claim 裏取り）と zeitgeist（複数の目）が同じ取得層を compose する。所有物＝CN火元カタログ（reference/sources.md）＋到達手段（WebSearch allowed_domains の cn 寄せ・Gemini 橋・直 WebFetch）＋ZHクエリ作法（中文語彙ブートストラップ・鮮度/canonical 軸）＋CN一次トピック判定の固有名リスト＋pick-best/ランキングガード。やらないこと＝取った素材の読み込み・裏取り・複数の目（要るなら deep-strict / zeitgeist へ）。Triggers — 「中国の源から取りたい」「CN火元」「中国系を取得」「中国で何が話されてる」。
---

CN 一次トピックを中文火元から取りに行く取得スキル。単独で完結して使える。

単独起動の流れ: トピックが CN 一次か判定 → ZH クエリを組む → 壁を越える → 火元カタログから引く → 取得素材を火元別に（タイトル/要点/リンク、取得失敗は理由付きで）返す。これがこのスキルの成果物。

deep-strict / zeitgeist から呼ばれたときは、同じ取得を供給し、読み込み・裏取り・複数の目は呼び出し側に委ねる。取った素材の解釈・corroboration・レンズ掛けには自分からは立ち入らない（要るなら呼び出し側がやる）。

## CN一次トピック判定

次のいずれかが一次ソースになるトピックは CN一次。英語二次は時差・翻訳ロス・西側バイアス込みなので一次の代替にしない。

- モデル/lab: DeepSeek・Qwen/通义・GLM/智谱・Kimi/月之暗面・MiniMax・豆包・Hunyuan/混元
- ハード/チップ: 昇腾・寒武纪・摩尔线程
- 制度/規制: 工信部・CAC(网信办)
- 企業/アプリ/市場/平替プロダクト

但し書き: CN lab は論文を arXiv に英語で出すので純・論文層は既存の英語経路でほぼ足りる。ZH 増強が効くのは非論文層——モデルカード・官方ブログ・公众号告知・知乎の深掘り・コミュニティ再現/批判。ここを狙う。

## 到達 — 壁越え

火元の種別（reference/sources.md の印）で経路を選ぶ。優先順は API > WebSearch > Gemini 橋 > 直ページ。

- API/RSS を持つ火元はエンドポイントを直 WebFetch（V2EX `api/topics/latest.json`・`hot.json`、Bilibili `api.bilibili.com/x/web-interface/popular`、36氪/少数派/IT之家 の `/feed`、CN agent フレームワークの GitHub Discussions。エンドポイントと露出フィールドは reference/sources.md）。本物の per-item タイムスタンプが取れる最良経路＝まずここを当てる。
- API の無い grey 火元は WebSearch の `allowed_domains` を cn ドメインに寄せる（zhihu.com / 36kr.com / juejin.cn / jiqizhixin.com / mp.weixin.qq.com 等。知乎の深掘り・机器之心・腾讯云/阿里云开发者 など）。この環境の WebSearch は US 寄りで CN に届きにくいのでドメイン寄せが要る。
- WebSearch で届かない velocity 源・動画系は Antigravity(Gemini) 橋で取る（WebSearch と並列）。
  - 撃ち方: `ask.py --timeout 240 "<CN/動画の velocity 上位を JSON 配列で ~/.claude/skills/cn-search/.cache/gemini.json に書け>"`。
  - 受け方: inline 返答は当てにしない（ブリッジの capture は書き込み完了前に返る）。出力ファイルの存在をリトライ確認し valid JSON になったら読む。
  - 承認の前提: handoff 先を `~/.claude/skills/cn-search/.cache/` 配下に固定する。Antigravity の承認は `~/.gemini/config/config.json` の `userSettings.globalPermissionGrants.allow` で決まり、`write_file(~/.claude/skills/cn-search/.cache/...)` が無いと毎回 Review 承認で固まる。セットアップ時にこの1行を append しておく。
- 個別の官方ページ・モデルカードは官方ブログ・GitHub・HuggingFace を直 WebFetch。

## ZHクエリ作法

ZH を撃つときの組み立て。

- 語彙ブートストラップを中文で 1 本（術語が英語と別: 大模型・推理・微调・评测・智能体・上下文・复现）。戻ったタイトルから術語を拾って本クエリに使う。
- 二軸に割る。鮮度軸 = literal「2026年MM月」/「2026-MM」（現在月で展開）。canonical 軸 = 日付なし「{topic} 原理 / 评测 / 复现」。
- 視点違い・否定軸も撃つ: 「{topic} 批评 / 局限」「{topic} 翻车 / 造假 / 夸大」「{topic} 复现失败 / 实测」。

## ソース pick-best 序列

同じ claim に複数候補があるときの優先順位。

1. arXiv / GitHub / HuggingFace モデルカード / 官方技术博客（EN・ZH 問わず）
2. 官方公众号告知（mp.weixin.qq.com）/ 官方文档
3. 著名技术媒体: 机器之心 / 量子位(QbitAI) / InfoQ 中国
4. 当事者・コミュニティ: 知乎の高票回答 / 掘金 — CSDN は質が低く最後の手段

ランキング媒体ガード: 微博热搜 / 知乎热榜 / 百度热搜 / 今日头条 は pre-ranked の単眼ランキングで per-item の信頼できるタイムスタンプが無く、順位は媒体の編集圧であって一次ではない。source に数えない。固有名・検索語の発見補助としてのみ使う。

## 火元カタログ

対象ドメイン・velocity 取得可否・到達実測ステータスは reference/sources.md。velocity を自前計算できる火元（per-item の本物タイムスタンプを持つもの）はそこで印を付ける。velocity の計算式と順位付けは呼び出し側（zeitgeist）が持つ。このレイヤーは「どの火元がタイムスタンプを露出するか」までを供給する。
