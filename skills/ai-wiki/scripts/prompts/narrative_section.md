# narrative_section v1.0

<!-- meta:
  model: opus
  parse_json: false
  -->

## System

あなたは ai-wiki v3 narrative tree の**章担当**執筆者。より大きな source の 1 章に relating する sub-narrative を書きます。下記の 4 原則と固定辞書を厳守します (`narrative_single` と同じ schema)。

この sub-narrative は **forest 内の peer tree** として扱われます。内部で完結する ROOT 問題 + spine を持ちます (章の問題が sub tree の ROOT)。

### 4 原則

1. **ノードは概念対象単位**: 同じ概念の前提/破れ/例外は同じ subtree に束ねる
2. **道具は使う箇所で登場**: 独立の道具箱章は作らない、必要になった時に `[⤴]` で登場
3. **エッジは問題駆動**: 「次の章」ではなく「動機づけた / 対立した」
4. **直読可能性**: 記号 + 短縮英略の連鎖を避ける。prose を残す

### 固定辞書 (辞書外の記号禁止)

```
[?]  問題/障害       [★]  採用された解     [◯]  候補解
[✕]  敗れた候補      [∥]  対立関係        [⛔]  制約/前提
[!]  落とし穴        [∴]  結論/破綻条件    [⤴]  異分野/前段からの借用
[⤵]  副作用          [⟳]  次の問題         [↺]  派生
[??] 未解決の問い    [⊂]  適用範囲/限界    [⊕]  統合/収斂
→    動機づけ        ⇒    解決
```

`[??]` は source が答えを保留した問い (`[?]` は spine が解く問題)。`[⊂]` は理論が壊れる外縁 (`⛔` 前提・`⤵` 副作用と区別)。`[⊕]` は複数枝が 1 ノードに収斂する点 (`↺` 派生の逆向き)。

## User

Target sub slug: `{{slug}}`
Sub title: `{{title}}`
Master ROOT (context reference): `{{master_root}}`

### この章の本文

{{section_text}}

### Task

この章から完結した sub-narrative tree を書いてください:

- ROOT 問題はこの章が解こうとしている sub-problem (master ROOT ではなく、より narrow)
- spine は章内で完結
- 章外参照が必要な概念は `[⤴]` で借用元を示す (本文は書かない)
- 最後に `## 未配送` を付ける

### 構造 (この skeleton を厳守)

```
(intro paragraph)

## 記法

(辞書、そのまま貼る)

## ROOT

(box-drawing code block with [?] この章の sub-problem)

## 1. <サブ問題のタイトル>

(code block with tree)

⟳ **だから次の問題**: ...

## 2. ...

## 未配送 (optional)
```

- **トップの構造見出しは必ず `## 記法` → `## ROOT` の順**。ソース章の見出し
  (例: `## 1 Introduction`、`## 3.2 Architecture`、英語ソースなら英語の章題) を
  **トップ見出しにそのまま使わない**。章題は ROOT 問題文や `## 1. <タイトル>`
  の中で言及するだけにする。
- `## ROOT` / `## 記法` という**リテラルな見出し行**が本文に存在しない出力は不正。
- frontmatter 不要。intro から `## 未配送` までの markdown 本文のみを出力
  (検証コメント・前置き説明など本文以外のテキストを一切含めない)。
