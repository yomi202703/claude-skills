# CN火元カタログ

呼び出し側が対象ドメイン・エンドポイント・到達手段を引くための表。`到達` 列は この環境での実測ステータス（proven=実際に取れた / probe=未検証、初回使用時に到達可否を確かめてから依存する）。velocity 計算可＝per-item の本物タイムスタンプを露出し呼び出し側が勢いを自前計算できる。velocity の式・順位付けは呼び出し側（zeitgeist）が持ち、このレイヤーは「どの火元が・どのフィールドでタイムスタンプを露出するか」までを供給する。

## velocity 計算可（per-item タイムスタンプ露出）

API/RSS を直に叩ける。velocity = score / 経過h を呼び出し側が created/pubdate から一様に計算して混ぜる。

| 火元 | エンドポイント | タイムスタンプ / score | 到達 | 備考 |
|------|----------------|------------------------|------|------|
| V2EX | `https://www.v2ex.com/api/topics/latest.json` / `hot.json` | created(unix) / replies | proven | hot.json は V2EX 自身の単眼ランキング＝順位は使わず created から再計算する素材として両方混ぜる。replies が小さく velocity が立たなくても一次知（製品の焼失譚・実地のエージェント設計知）は呼び出し側の「新着・勢い未確定」枠で拾う |
| Bilibili 人気 | `https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1` | `list[].pubdate`(unix) / `stat.view`・`like`・`danmaku` | proven | 動画の実演・実測が出る層。owner/bvid/title 付き。velocity = view(or like)/経過h |
| 36氪 | `https://36kr.com/feed`（RSS） | `pubDate` | proven | 業界動向・lab 横断調査。score はフィードに無いので created のみ＝新着順／✨枠で扱う |
| 少数派 sspai | `https://sspai.com/feed`（RSS） | `pubDate` | proven | 消費者寄り tech だが AI ワークフロー記事が出る |
| IT之家 ithome | `https://www.ithome.com/rss/`（RSS） | `pubDate` | proven | 速報系 tech ニュース。AI/モデル告知を拾う |
| 掘金/Juejin | recommend API は POST ルートで頻繁に変わる | — | probe | GET で取れなければ grey 扱い |

RSS（36氪・少数派・IT之家）は score を持たないので、velocity の分子が無い＝created だけで新着順に並べ、勢い判定は付けず「✨新着・勢い未確定」枠で出す。score を持つのは V2EX(replies) と Bilibili(view/like)。

## grey（WebSearch 到達・clean な velocity なし）

`allowed_domains` を下のドメインに寄せて WebSearch で取る。

| 火元 | ドメイン | 到達 | 備考 |
|------|----------|------|------|
| 知乎（深掘り） | zhuanlan.zhihu.com / zhihu.com | proven | 高票回答・専欄。pick-best コミュニティ層 |
| 腾讯云开发者 | cloud.tencent.com/developer | proven | 実測記事・横評 |
| 阿里云开发者 | developer.aliyun.com | proven | 同上 |
| 机器之心 | jiqizhixin.com | proven(grey) | RSS 無し（HTML・login prompt）＝WebSearch か個別記事を直 WebFetch。著名技术媒体 |
| 量子位(QbitAI) | qbitai.com | probe | 著名技术媒体 |
| InfoQ 中国 | infoq.cn | probe | 著名技术媒体 |
| CSDN | csdn.net | proven | 質が低く最後の手段 |
| 官方公众号 | mp.weixin.qq.com | probe | 官方告知。login-wall に当たりやすい→官方ブログ/GitHub へ退避 |
| 个人公众号（高信号・発見ヒント） | mp.weixin.qq.com | probe | 宝玉xp(=宝玉的分享, X@dotey) / 归藏的AI工具箱(X@op7418) / AI工程化 / 凌十一 / LangGPT(云中江树) / AGI课堂。qwen+GLM 両モデルが挙げた名は高信頼。直 fetch は不安定＝著者名で WebSearch、知乎/CSDN ミラー経由で本文を拾う |

## CN agent フレームワークの GitHub Discussions（直 WebFetch・per-item 日付あり）

実戦級の Agent/RAG/Context 工程の一線が集まる。HTML だが各 discussion に created 日付があり新着順に拾える。score は無いので「✨新着」枠。

| 火元 | URL | 到達 | 備考 |
|------|-----|------|------|
| Dify | `github.com/langgenius/dify/discussions` | proven | 中英混在。Workflow 編成・長文 Context 截断の踏み台 |
| RAGFlow(InfiniFlow) | `github.com/infiniflow/ragflow/discussions` | proven | 文書解析・Chunking 戦略＝Context Engineering の濃い層 |
| FastGPT | `github.com/labring/FastGPT/discussions` | proven | RAG/Agent 落地 |
| MaxKB | `github.com/1Panel-dev/MaxKB/discussions` | probe | Memory/多 Agent 協調の議論 |

## 官方・一次（直 WebFetch）

| 対象 | 取得 | 備考 |
|------|------|------|
| AI lab 官方 | 官方技术博客 / GitHub / HuggingFace モデルカード | DeepSeek・Qwen/通义・GLM/智谱・Kimi/月之暗面・MiniMax・豆包・Hunyuan。pick-best 最上位 |

## ランキング媒体（source に数えない・発見補助のみ）

pre-ranked の単眼ランキングで per-item の信頼できるタイムスタンプ無し。固有名・検索語の発見にだけ使う。

- 微博热搜 — `m.weibo.cn` の hot 系は visitor passport へ 302（認証壁）で直叩き不可。固有名の発見に使うなら Gemini 橋経由か、トレンド語を拾って他火元へ展開
- 知乎热榜 / 百度热搜 / 今日头条

## 人手枠（fetch 対象外・あなた個人の辺境アクセス）

機械では取れない（app/login 壁・参加制）が、CN ネイティブ層が実際に密集する場。fetch せず、何が話されているかを掴む人手の窓口として持つ。

- 即刻 圈子: AI产品探索 / AIGC / AI产品榜 / AI造物主（独立開発者・Agent 基建の実地踩坑）
- 小红书 話題: #AI独立开发 / #Cursor（コード截図＋報错ログの実操ノート。「最新」順、営销号を除く）
- 小宇宙 播客: OnBoard!（qwen+GLM 両推し）/ 张小珺的科技产品杂谈 / 十字路口Crossing / 硅谷101。shownotes に群の二維碼
- 知识星球（有料）: AI破局俱乐部 / LangGPT「云中江树」/ 出海AI / 大模型应用开发实战
- 参加制コミュニティ: Dify/FastGPT 官方飞书・Discord / Moonshot(Kimi) Discord / 厂の内测群 / Telegram（X の @op7418・@dotey 経由でリンクが流れる）/ Hackathon 赛后群

## 種出しの回し方

qwen-web / glm-web（CN ネイティブ・非相関）に「定番外で高水準 AI 从业者が集まる圏子」を吐かせる→機械到達するものは上の表へ実測昇格、参加制は人手枠へ。2 モデルが共に挙げた名は高信頼。Western モデルが出さない辺境を埋める用途。
