from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from . import stability
from .emit import targets

RULES_PATH = Path("ai-rules/rules.yml")

TEMPLATE = """\
# AIコンテキストのマスタ。ここだけを手で編集する。
# 各ツール向けの規約ファイルは `ai-rules build` が生成する。手で触らない。

# 配布先。使っていないツールは false にする。
outputs:
  claude: true    # .claude/rules/<layer>.md      （paths: でスコープ）
  cursor: false   # .cursor/rules/<layer>.mdc     （globs でスコープ）
  copilot: false  # .github/copilot-instructions.md（スコープ機能なし。全層を1ファイルに集約）

# 全レイヤーに配布される共通規約。
# 追加するときは、既存の1行を削れないか先に検討すること。
# 指示は増えるほど1行あたりの効力が薄まる。
common:
  - 例外は握りつぶさない。上位に伝播させるか、明示的にログを残す
  - 外部入力は境界で検証する。内部関数では呼び出し元を信頼する
  - 抽象化より重複を選ぶ。3回目の重複で初めて抽象化を検討する

layers:
  domain:
    path: src/domain
    description: ビジネスルールを表現する層。この層だけを読めば業務が理解できる状態を保つ。
    rules:
      - 外部ライブラリを import しない（標準ライブラリと自層の型のみ）
      - I/O を行わない。DB・HTTP・ファイルアクセスはこの層に存在しない
"""


def load_config() -> dict:
    if not RULES_PATH.exists():
        print(f"マスタが見つかりません: {RULES_PATH}", file=sys.stderr)
        print("`ai-rules init` で雛形を作れます。", file=sys.stderr)
        raise SystemExit(1)
    try:
        return yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"{RULES_PATH} のYAMLが壊れています:\n{exc}", file=sys.stderr)
        raise SystemExit(1)


def cmd_init(_args) -> int:
    if RULES_PATH.exists():
        print(f"すでに存在します: {RULES_PATH}", file=sys.stderr)
        return 1
    RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RULES_PATH.write_text(TEMPLATE, encoding="utf-8")
    print(f"created: {RULES_PATH}")
    print("layers を自分のディレクトリ構成に合わせて書き換えてから `ai-rules build` を実行してください。")
    return 0


def cmd_build(_args) -> int:
    for path, content in targets(load_config()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"generated: {path}")
    return 0


def cmd_check(_args) -> int:
    planned = targets(load_config())
    stale = [
        path
        for path, content in planned
        if not path.exists() or path.read_text(encoding="utf-8") != content
    ]
    if stale:
        print("AIコンテキストが古い、または欠落しています:", file=sys.stderr)
        for path in stale:
            print(f"  {path}", file=sys.stderr)
        print("\n`ai-rules build` を実行してコミットしてください", file=sys.stderr)
        return 1
    print(f"OK: {len(planned)} 件の生成物は最新です")
    return 0


def cmd_stability(args) -> int:
    command = args.command[1:] if args.command and args.command[0] == "--" else args.command
    if not command:
        print("`--` のあとにレビューコマンドを指定してください", file=sys.stderr)
        return 2
    return stability.measure(command, args.runs)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ai-rules",
        description="1つのマスタから Claude Code / Cursor / Copilot 向けの規約を生成し、CIで検証する",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="ai-rules/rules.yml の雛形を作る").set_defaults(func=cmd_init)
    sub.add_parser("build", help="各ツール向けの規約ファイルを生成する").set_defaults(func=cmd_build)
    sub.add_parser("check", help="生成物が最新かを検証する（CI用・書き込まない）").set_defaults(func=cmd_check)

    p = sub.add_parser("stability", help="同じ入力でN回走らせ、指摘の安定性を測る")
    p.add_argument("--runs", type=int, default=3, help="実行回数（既定3）")
    p.add_argument("command", nargs=argparse.REMAINDER, help="-- のあとにレビューコマンド")
    p.set_defaults(func=cmd_stability)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
