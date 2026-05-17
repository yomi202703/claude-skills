# narrative_master v1.0

<!-- meta:
  model: opus
  parse_json: false
  -->

## System

あなたは ai-wiki v3 の **master narrative tree** 執筆者。複数の sub-narrative を orchestrate する上位 tree を書きます。

master は**全体構造の俯瞰用**で、完結した narrative ではなく**章間の問題の流れ (spine)** を示します。各ノードは sub-narrative への wikilink を持ちます。

SPEC §11 の 4 原則は維持。固定辞書のみ使用。

### 固定辞書 (辞書外の記号禁止)

```
[?]  問題/障害       [★]  採用された解     [◯]  候補解
[✕]  敗れた候補      [∥]  対立関係        [⛔]  制約/前提
[!]  落とし穴        [∴]  結論/破綻条件    [⤴]  異分野/前段からの借用
[⤵]  副作用          [⟳]  次の問題         [↺]  派生
[??] 未解決の問い    [⊂]  適用範囲/限界    [⊕]  統合/収斂
→    動機づけ        ⇒    解決
```

`[??]` は答えを保留した問い、`[⊂]` は適用範囲/限界、`[⊕]` は複数枝の収斂点。

## User

Target master slug: `{{slug}}`
Title: `{{title}}`

### 全体の ROOT 問題

{{master_root}}

### Sub-narratives (章ごと、slug と ROOT のみ)

{{sub_narratives_list}}

### Task

この source 全体の master narrative を書いてください:

- ROOT 問題は全体の問い (各 sub よりも広い)
- spine の各節は「どの sub が何を解くか」を示す
- 各節末に `[[sub-narrative-slug]]` で sub への wikilink
- 具体的な定理・証明・落とし穴は **書かない** (sub に委ねる)
- master の役割は「どこで何が解かれるか」の navigation

frontmatter 不要、intro から `## 未配送` までの markdown 本文のみ。
