"""同じ入力でレビューを N 回走らせ、出力の安定性を測る。

正解データを用意せず「自己一致」だけを見るので、導入コストがほぼゼロで済む。
High の指摘が実行ごとにブレるなら、それはモデルの気まぐれではなく
入力の制御に失敗しているというシグナル。
"""

from __future__ import annotations

import json
import subprocess
import sys
from itertools import combinations

# 安定していることを期待する重大度。ここがブレたら入力制御を疑う。
CRITICAL = {"high", "critical"}


def extract(payload) -> list[dict]:
    if isinstance(payload, dict):
        for key_name in ("findings", "issues", "results"):
            if isinstance(payload.get(key_name), list):
                return payload[key_name]
        return []
    return payload if isinstance(payload, list) else []


def key(finding: dict) -> tuple:
    """行番号は実行ごとに1〜2行ずれることがあるので、同一性の判定には使わない。"""
    return (
        str(finding.get("file", "")),
        str(finding.get("category", "")).lower(),
        str(finding.get("severity", "")).lower(),
    )


def run_once(command: list[str], index: int) -> set[tuple] | None:
    proc = subprocess.run(command, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"[{index}] コマンドが失敗しました (exit {proc.returncode})", file=sys.stderr)
        print(proc.stderr.strip()[:2000], file=sys.stderr)
        return None
    try:
        findings = extract(json.loads(proc.stdout))
    except json.JSONDecodeError as exc:
        print(f"[{index}] JSONとして解釈できません: {exc}", file=sys.stderr)
        return None
    return {key(f) for f in findings if str(f.get("severity", "")).lower() in CRITICAL}


def measure(command: list[str], runs: int) -> int:
    results = []
    for i in range(1, runs + 1):
        print(f"実行 {i}/{runs} ...", file=sys.stderr)
        result = run_once(command, i)
        if result is None:
            return 2
        results.append(result)
        print(f"  High/Critical: {len(result)} 件", file=sys.stderr)

    union = set().union(*results)
    intersection = set.intersection(*results)
    unstable = union - intersection

    print()
    print(f"全実行で一致した指摘 : {len(intersection)} 件")
    print(f"実行ごとにブレた指摘 : {len(unstable)} 件")

    if not union:
        print("\nHigh/Critical の指摘が1件も出ていません。")
        print("安定性は測れていません。まず指摘が出る差分に対して実行してください。")
        return 0

    if unstable:
        print("\nブレた指摘:")
        for path, category, severity in sorted(unstable):
            appeared = [str(i) for i, r in enumerate(results, 1) if (path, category, severity) in r]
            print(f"  [{severity}] {path} ({category}) — 実行 {','.join(appeared)} のみ")

        worst = max(len(a ^ b) for a, b in combinations(results, 2))
        print(f"\n最大対称差分: {worst} 件")
        print("入力が実行ごとに変わっている可能性があります。以下を確認してください:")
        print("  - 会話履歴が混入していないか（ヘッドレスで起動しているか）")
        print("  - 読み込むファイルが実行ごとに変わっていないか")
        print("  - プロンプトに時刻やランダム要素が入っていないか")
        return 1

    print("\n安定しています。入力の制御ができています。")
    return 0
