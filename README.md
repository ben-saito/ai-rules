# ai-rules

1つのマスタから **Claude Code / Cursor / GitHub Copilot** 向けのコーディング規約を生成し、
更新漏れを **CIの赤** で検知する、Python 製の CLI です。

```bash
pip install git+https://github.com/ben-saito/ai-rules
```

> **⚠️ `pip install ai-rules` は実行しないでください。**
> PyPI の `ai-rules` は**別の作者の無関係なパッケージ**です。PyPI への公開名は未定です。

---

## 先に、これを使わないほうがいいケースを書きます

### 1. 規約を生成したいだけなら → [`intellectronica/ruler`](https://github.com/intellectronica/ruler) か [`dyoshikawa/rulesync`](https://github.com/dyoshikawa/rulesync)

**この用途は既に解決済みです。まず既存ツールを検討してください。**

| | ruler | rulesync | ai-rules（これ） |
|---|---|---|---|
| スター | ★2.8k | ★1.3k | — |
| 対応ツール | 20以上 | Claude Code / Cursor / Cline / Copilot ほか | Claude Code / Cursor / Copilot |
| 生成対象 | rules, ignore, mcp | rules, ignore, mcp, commands, subagents, skills, hooks, permissions | **rules のみ** |
| 実行環境 | Node.js | Node.js | **Python（依存は PyYAML 1つ）** |
| 安定性の測定 | なし | なし | `stability` あり |

対応範囲で勝てる要素はありません。**このツールが要るのは次の2つだけです。**

- **リポジトリに Node を持ち込みたくない**（Python プロジェクトの CI に `npx` を足したくない、など）
- **`stability`（規約の効果を正解データなしで測る）を使いたい**

### 2. Claude Code しか使っていないなら → 公式の `.claude/rules/`

`paths:` フロントマターでディレクトリごとに規約をスコープできる、よくできた機能です。
**単一ツール運用なら、生成の仕組みそのものが不要です。**

---

このツールの前提は、**複数のAIコーディングツールが混在していて、かつ Python で完結させたい**環境です。

| ツール | 置き場所 | スコープの指定 |
|---|---|---|
| Claude Code | `.claude/rules/<層>.md` | `paths:` フロントマター |
| Cursor | `.cursor/rules/<層>.mdc` | `globs:` フロントマター |
| GitHub Copilot | `.github/instructions/<層>.instructions.md` | `applyTo:` フロントマター |

3ツールともディレクトリ単位のスコープを持っていますが、**置き場所も拡張子もキー名も全部違います。**
同じ規約を3箇所に手で書けば、**必ずズレます。** そしてズレても誰も気づきません。

Copilot だけは共通規約の置き場所が別で、`.github/copilot-instructions.md` に出します
（このファイルにはスコープがなく、リポジトリ全体に効きます）。

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
  cursor: true    # 雛形では false。使っているツールだけ true にする
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

レイヤーをリネーム・削除すると、旧ファイルは `build` が消します。

```
removed: .claude/rules/domain.md（マスタに対応するレイヤーがありません）
```

消さずに残すと、**古い規約と新しい規約が同時にロードされます。**
矛盾する指示が両方効くので、この削除は安全側の挙動ではなく必須の挙動です。
（削除対象は先頭に `DO NOT EDIT` マーカーを持つファイルだけです。手書きのファイルは消しません。）

生成物は `.gitignore` に**入れません。** エージェントは実行時にファイルシステムを読むので、
リポジトリに存在している必要があります。

### 3. CIで検証する

```bash
ai-rules check
```

終了コード **1** で落ちるのは次の3つです。

1. `rules.yml` を直して再生成し忘れた（生成物が古い、または無い）
2. マスタに対応するレイヤーがない生成物が残っている（リネーム・削除の取りこぼし）
3. `rules.yml` の `path` が実在しない

3つ目は**最も静かに壊れるパターン**です。ディレクトリを移動するとグロブが一致しなくなりますが、
生成は成功したままで、規約だけが一度も適用されなくなります。これはエラーになりません。だから CI で見ます。

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

## 出力の安定性を測る（`stability`）

規約の生成ツールは、規約が*配られたこと*は保証しますが、*効いたこと*は保証しません。
`stability` は正解データなしで、出力がブレていないかだけを見ます。

繰り返し実行してブレを見る仕組み自体は既にあります（LangSmith の `num_repetitions`、promptfoo の `--repeat` など）。
ただしどちらも評価基盤の導入が前提です。`stability` は**評価基盤なしで、既存のレビューコマンドにそのまま被せる**ことだけを狙っています。

`ai-rules` を規約生成に使っていなくても、このコマンドだけ単独で使えます（`rules.yml` を必要としません）。

```bash
ai-rules stability --runs 3 -- your-review-command --format json
```

同じ入力で N 回走らせ、**High / Critical の指摘の集合が一致するか**だけを見ます。
正解データを用意しないので導入コストがほぼゼロです。

`--` のあとは任意のコマンドで構いません。
標準出力に `[{...}]` か、`findings` / `issues` / `results` / `violations` / `problems` / `diagnostics`
のいずれかのキーに配列を持つ JSON を吐けば動きます。
各要素は `file` / `severity` / `category` と、本文（`message` / `title` / `description` のいずれか）を持っていることを期待します。
本文まで見て同一性を判定するので、**同じファイルに毎回違う指摘が出る場合もブレとして検出します。**

指摘があると非ゼロ終了するツール（多くのリンタがそうです）でも、JSON が読めていれば正常に扱います。

指摘がブレたら、**モデルを疑う前に入力を疑ってください。** 原因はほぼ次の3つです。

1. 会話履歴が混入している（ヘッドレスで起動していない）
2. 読み込むファイルが実行ごとに変わっている
3. プロンプトに時刻やランダム要素が入っている

終了コードは 0=安定 / 1=ブレあり / 2=コマンドかJSONの失敗 / **3=測れていない**。

`3` は High/Critical の指摘が1件も出なかった場合です。**これを「安定」と読まないでください。**
指摘が出る差分に対して実行し直す必要があります。

---

## つまずきやすいところ

**生成物を手で直したら次の生成で消えた**

仕様です。マスタは `ai-rules/rules.yml` だけ。生成物の先頭に `DO NOT EDIT` が入っているのはそのためです。

**`check` がローカルで通るのにCIで落ちる**

改行コードです。`.gitattributes` に `*.md text eol=lf` を入れてください。

**Copilot で層ごとの規約が効かない**

`.github/instructions/` が使えるのは比較的新しいバージョンです。
古い環境では `.github/copilot-instructions.md` しか読まれず、そこには共通規約しか入っていません
（層ごとの規約は `applyTo:` 付きの `instructions/` 側にあります）。
層の規約まで全体に効かせたいなら、その分は `common` に移してください。

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

同じ作者の関連OSS: [`ben-saito/revi`](https://github.com/ben-saito/revi) — 決定論的に制御するAIコードレビューCLI（MIT）

## ライセンス

MIT
