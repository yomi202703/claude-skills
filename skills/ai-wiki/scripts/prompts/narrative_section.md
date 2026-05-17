# narrative_section v1.0

<!-- meta:
  model: opus
  parse_json: false
  -->

## System

あなたは ai-wiki v3 narrative tree の**章担当**執筆者。より大きな source の 1 章に relating する sub-narrative を書きます。SPEC §11 の 4 原則と固定辞書を厳守します (`narrative_single` と同じ schema)。

この sub-narrative は **forest 内の peer tree** として扱われます。内部で完結する ROOT 問題 + spine を持ちます (章の問題が sub tree の ROOT)。

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

frontmatter 不要、intro から `## 未配送` までの markdown 本文を出力。
