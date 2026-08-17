# ai-rules

1つのマスタから **Claude Code / Cursor / GitHub Copilot** 向けのコーディング規約を生成し、
更新漏れを **CIの赤** で検知する CLI です。

```bash
pip install git+https://github.com/ben-saito/ai-rules
```

> **⚠️ `pip install ai-rules` は実行しないでください。**
> PyPI の `ai-rules` は**別の作者の無関係なパッケージ**です。PyPI への公開名は未定です。

---

## 先に、これが要らないケースを書きます

**規約の生成そのものは [`dyoshikawa/rulesync`](https://github.com/dyoshikawa/rulesync)（★1.3k）が既に成熟しています。**
Claude Code / Cursor / Cline / Copilot に対応し、rules だけでなく mcp・commands・subagents・skills・hooks・permissions まで生成します。
**生成が目的なら、まず rulesync を検討してください。**

**Claude Code には `.claude/rules/` という公式の仕組みがあります。**
`paths:` フロントマターでディレクトリごとに規約をスコープできる、よくできた機能です。

**Claude Code しか使っていないなら、公式機能をそのまま使ってください。このツールは要りません。**

このツールの前提は、**複数のAIコーディングツールが混在している**環境です。

| ツール | 置き場所 | フォーマット | スコープ |
|---|---|---|---|
| Claude Code | `.claude/rules/*.md` | `paths:` フロントマター | ディレクトリ単位 |
| Cursor | `.cursor/rules/*.mdc` | `globs:` フロントマター | ディレクトリ単位 |
| GitHub Copilot | `.github/copilot-instructions.md` | 単一ファイル | **スコープ機能なし** |

置き場所もフォーマットもスコープの有無も全部違います。
同じ規約を3箇所に手で書けば、**必ずズレます。** そしてズレても誰も気づきません。

やることは2つだけです。

1. 規約を `ai-rules/rules.yml` 1つに集約し、各ツールの形式へ生成する
2. 生成物が古くなっていないかを CI で検証する

---

## 使い方

### 1. マスタを作る

```bash
ai-rules init
```

`ai-rules/rules.yml` が生成されます。`layers` を自分のディレクトリ構成に合わせて書き換えてください。

```yaml
outputs:
  claude: true
  cursor: true
  copilot: false

# 全レイヤーに配布される共通規約
common:
  - 例外は握りつぶさない。上位に伝播させるか、明示的にログを残す
  - 外部入力は境界で検証する。内部関数では呼び出し元を信頼する

layers:
  domain:
    path: src/domain
    description: ビジネスルールを表現する層。この層だけを読めば業務が理解できる状態を保つ。
    rules:
      - 外部ライブラリを import しない（標準ライブラリと自層の型のみ）
      - I/O を行わない。DB・HTTP・ファイルアクセスはこの層に存在しない
```

### 2. 生成する

```bash
ai-rules build
```

```
generated: .claude/rules/domain.md
generated: .cursor/rules/domain.mdc
```

既存の `.claude/rules/` や `.cursor/rules/` は**上書きされます。**
手で書いた内容は先に `rules.yml` へ移してください。

生成物は `.gitignore` に**入れません。** エージェントは実行時にファイルシステムを読むので、
リポジトリに存在している必要があります。

### 3. CIで検証する

```bash
ai-rules check
```

`rules.yml` を直して再生成し忘れると、終了コード **1** で落ちます。

```yaml
# .github/workflows/ai-rules.yml
name: ai-rules
on: [pull_request, push]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/ben-saito/ai-rules
      - run: ai-rules check
```

これで、更新漏れの検知が**人間の注意力から機械の保証**に変わります。

---

## おまけ: 出力の安定性を測る

規約を整えた効果を、正解データなしで測るコマンドも入っています。

```bash
ai-rules stability --runs 3 -- your-review-command --format json
```

同じ入力で N 回走らせ、**High / Critical の指摘の集合が一致するか**だけを見ます。
正解データを用意しないので導入コストがほぼゼロです。

`--` のあとは任意のコマンドで構いません。
標準出力に `[{...}]` または `{"findings": [{...}]}` の形で JSON を吐けば動きます。
各要素は `file` / `severity` / `category` を持っていることを期待します。

指摘がブレたら、**モデルを疑う前に入力を疑ってください。** 原因はほぼ次の3つです。

1. 会話履歴が混入している（ヘッドレスで起動していない）
2. 読み込むファイルが実行ごとに変わっている
3. プロンプトに時刻やランダム要素が入っている

終了コードは 0=安定 / 1=ブレあり / 2=コマンドかJSONの失敗。

---

## つまずきやすいところ

**生成物を手で直したら次の生成で消えた**

仕様です。マスタは `ai-rules/rules.yml` だけ。生成物の先頭に `DO NOT EDIT` が入っているのはそのためです。

**`check` がローカルで通るのにCIで落ちる**

改行コードです。`.gitattributes` に `*.md text eol=lf` を入れてください。

**Copilot だけ規約が守られない**

Copilot の `.github/copilot-instructions.md` には**スコープ機能がありません。**
全層の規約が1ファイルに集約されるため、ファイル数が増えるほど1行あたりの効力が薄まります。
Copilot をメインで使うなら `common` を3行以内に絞ってください。

**規約を足したら守られなくなった**

想定内です。指示は増えるほど1行あたりの効力が薄まります。**足すときは削る**、が唯一の運用ルールです。

**Windsurf / Cline にも配りたい**

`src/ai_rules/emit.py` の `EMITTERS` に1関数足すだけです。
`emit_cursor` をコピーして、置き場所とフロントマターを変えてください。PR歓迎です。

---

## なぜこれを作ったか

背景と設計の考え方は記事に書いています。

- [AIエージェント駆動開発におけるリポジトリ構造変更と、AIコンテキストの整合性維持の課題](https://zenn.dev/tsutomusaito/articles/2026-05-10-f4e76d86)
- [AIによるレビュー精度を保つ方法](https://zenn.dev/tsutomusaito/articles/ai-2026-05-11-5b1c0152)

<!-- 旗艦記事の公開後に追記すること:
- [AIエージェントが「知っているはず」を間違える理由](https://zenn.dev/tsutomusaito/articles/ai-agent-context-design)
公開前に載せるとリンクが404になる。リポジトリのpushが記事公開より先なので順序に注意。 -->

同じ作者の関連OSS: [`ben-saito/revi`](https://github.com/ben-saito/revi) — 決定論的に制御するAIコードレビューCLI（MIT）

## ライセンス

MIT
