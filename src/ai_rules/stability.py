"""同じ入力でレビューを N 回走らせ、出力の安定性を測る。

正解データを用意せず「自己一致」だけを見るので、導入コストがほぼゼロで済む。
High の指摘が実行ごとにブレるなら、それはモデルの気まぐれではなく
入力の制御に失敗しているというシグナル。

終了コード: 0=安定 / 1=ブレあり / 2=コマンドかJSONの失敗 / 3=測れていない
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from itertools import combinations

# 安定していることを期待する重大度。ここがブレたら入力制御を疑う。
CRITICAL = {"high", "critical"}

LIST_KEYS = ("findings", "issues", "results", "violations", "problems", "diagnostics")


class ExtractError(Exception):
    """出力は JSON だが、指摘の配列が見つからない。"""


def extract(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key_name in LIST_KEYS:
            if isinstance(payload.get(key_name), list):
                return payload[key_name]
        raise ExtractError(
            f"指摘の配列が見つかりません。トップレベルのキー: {sorted(payload)}\n"
            f"期待するキー: {', '.join(LIST_KEYS)}、または配列そのもの"
        )
    raise ExtractError(f"配列でもオブジェクトでもありません: {type(payload).__name__}")


def key(finding: dict) -> tuple:
    """行番号は実行ごとに1〜2行ずれることがあるので、同一性の判定には使わない。

    指摘の本文は含める。同じファイルの別の問題を同一視すると、
    毎回違う指摘が返っていても「一致」と読めてしまう。
    """
    text = finding.get("message") or finding.get("title") or finding.get("description") or ""
    return (
        str(finding.get("file", "")),
        str(finding.get("category", "")).lower(),
        str(finding.get("severity", "")).lower(),
        re.sub(r"\s+", " ", str(text)).strip().lower(),
    )


def run_once(command: list[str], index: int) -> Counter | None:
    proc = subprocess.run(command, capture_output=True, text=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        # 指摘があると非ゼロ終了するツールは多い。JSONが読めた場合のみ終了コードを許す
        if proc.returncode != 0:
            print(f"[{index}] コマンドが失敗しました (exit {proc.returncode})", file=sys.stderr)
            print(proc.stderr.strip()[:2000], file=sys.stderr)
        else:
            print(f"[{index}] JSONとして解釈できません: {exc}", file=sys.stderr)
        return None
    try:
        findings = extract(payload)
    except ExtractError as exc:
        print(f"[{index}] {exc}", file=sys.stderr)
        return None
    return Counter(key(f) for f in findings if str(f.get("severity", "")).lower() in CRITICAL)


def measure(command: list[str], runs: int) -> int:
    results = []
    for i in range(1, runs + 1):
        print(f"実行 {i}/{runs} ...", file=sys.stderr)
        result = run_once(command, i)
        if result is None:
            return 2
        results.append(result)
        print(f"  High/Critical: {sum(result.values())} 件", file=sys.stderr)

    # 件数もブレとして数える。3件→1件を「一致」と読ませない
    # &= は Counter をその場で書き換えるので、results[0] を直接渡さない
    intersection = results[0].copy()
    union = Counter()
    for r in results:
        intersection &= r
        union |= r
    unstable = union - intersection

    print()
    print(f"全実行で一致した指摘 : {sum(intersection.values())} 件")
    print(f"実行ごとにブレた指摘 : {sum(unstable.values())} 件")

    if not union:
        print("\nHigh/Critical の指摘が1件も出ていません。")
        print("安定性は測れていません。まず指摘が出る差分に対して実行してください。")
        return 3

    if unstable:
        print("\nブレた指摘:")
        for entry in sorted(unstable):
            path, category, severity, text = entry
            counts = [f"{i}:{results[i - 1][entry]}" for i in range(1, len(results) + 1)]
            label = f"{path} ({category})" if category else path
            if text:
                label += f" — {text[:60]}"
            print(f"  [{severity}] {label}")
            print(f"      実行ごとの件数: {' '.join(counts)}")

        worst = max(sum(((a - b) + (b - a)).values()) for a, b in combinations(results, 2))
        print(f"\n最大対称差分: {worst} 件")
        print("入力が実行ごとに変わっている可能性があります。以下を確認してください:")
        print("  - 会話履歴が混入していないか（ヘッドレスで起動しているか）")
        print("  - 読み込むファイルが実行ごとに変わっていないか")
        print("  - プロンプトに時刻やランダム要素が入っていないか")
        return 1

    print("\n安定しています。入力の制御ができています。")
    return 0
