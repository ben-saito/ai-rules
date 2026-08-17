"""1つのマスタ（rules.yml）から、各AIコーディングツール向けの規約ファイルを生成する。

ツールごとに置き場所もフロントマターのキーも違う:

    Claude Code    .claude/rules/<layer>.md                  paths: フロントマター
    Cursor         .cursor/rules/<layer>.mdc                 globs: フロントマター
    GitHub Copilot .github/instructions/<layer>.instructions.md  applyTo: フロントマター

同じ規約を3箇所に手で書くと必ずズレる。そしてズレても誰も気づかない。
"""

from __future__ import annotations

from pathlib import Path

MARKER = "GENERATED from ai-rules/rules.yml — DO NOT EDIT"


def body(name: str, layer: dict, common: list[str]) -> str:
    """ツール共通の本文。フロントマターは各エミッタが付ける。"""
    lines = [f"# {name} 層", "", layer["description"].strip(), "", "## この層の規約"]
    lines += [f"- {rule}" for rule in layer["rules"]]
    lines += ["", "## 全体共通"]
    lines += [f"- {rule}" for rule in common]
    return "\n".join(lines)


def glob_for(layer: dict) -> str:
    return f"{layer['path'].rstrip('/')}/**/*"


def emit_claude(config: dict) -> list[tuple[Path, str]]:
    out = []
    for name, layer in config["layers"].items():
        content = (
            f"---\npaths:\n  - \"{glob_for(layer)}\"\n---\n\n"
            f"<!-- {MARKER} -->\n\n{body(name, layer, config['common'])}\n"
        )
        out.append((Path(".claude/rules") / f"{name}.md", content))
    return out


def emit_cursor(config: dict) -> list[tuple[Path, str]]:
    out = []
    for name, layer in config["layers"].items():
        description = layer["description"].strip().splitlines()[0]
        content = (
            f"---\ndescription: {description}\nglobs: {glob_for(layer)}\nalwaysApply: false\n---\n\n"
            f"<!-- {MARKER} -->\n\n{body(name, layer, config['common'])}\n"
        )
        out.append((Path(".cursor/rules") / f"{name}.mdc", content))
    return out


def emit_copilot(config: dict) -> list[tuple[Path, str]]:
    """共通規約は copilot-instructions.md、層ごとの規約は instructions/ に applyTo 付きで出す。

    Copilot は .github/instructions/<name>.instructions.md の applyTo: でグロブ指定できる。
    共通規約だけを全体ファイルに残すことで、層の規約が他の層を薄めない。
    """
    common_body = "\n".join(
        [f"<!-- {MARKER} -->", "", "# コーディング規約（全体共通）", ""]
        + [f"- {rule}" for rule in config["common"]]
    )
    out = [(Path(".github/copilot-instructions.md"), common_body + "\n")]

    for name, layer in config["layers"].items():
        content = (
            f'---\napplyTo: "{glob_for(layer)}"\n---\n\n'
            f"<!-- {MARKER} -->\n\n{body(name, layer, config['common'])}\n"
        )
        out.append((Path(".github/instructions") / f"{name}.instructions.md", content))
    return out


EMITTERS = {"claude": emit_claude, "cursor": emit_cursor, "copilot": emit_copilot}


def targets(config: dict) -> list[tuple[Path, str]]:
    enabled = config.get("outputs") or {"claude": True}
    unknown = set(enabled) - set(EMITTERS)
    if unknown:
        raise SystemExit(f"outputs に未知のツールがあります: {sorted(unknown)}（有効: {sorted(EMITTERS)}）")

    # レイヤー名はそのままファイル名になる。区切り文字を許すと生成先の外に書き出せてしまう
    for name in config["layers"]:
        if not name or "/" in name or "\\" in name or name.startswith("."):
            raise SystemExit(f"レイヤー名に使えない文字が含まれています: {name!r}（/ \\ . を含まない名前にしてください）")
    out = []
    for tool, emitter in EMITTERS.items():
        if enabled.get(tool):
            out.extend(emitter(config))
    return out
