"""handoff-hooks を Claude Code・Codex・Antigravity(agy)へ入れる(外す)。

- hook(hooks/*.py)と雛形(templates/handoff/)を ~/.handoff-hooks へ写す。3つの道具はそこを使う。
- 決まり(rules/handoff.md)を各道具の全体の指示ファイルへ、目印の行で囲んだ区画として入れる(区画の外は触らない)。
- hook の登録を ~/.claude/settings.json・~/.codex/hooks.json・~/.gemini/config/hooks.json へ合わせる(他の hook・設定は残す)。
変えるファイルは、変える前に同じフォルダへ <名前>.bak-handoff-hooks-<日時> として残す。

使い方:
  python install.py                      入れる(道具は ~/.claude・~/.codex・~/.gemini があるものだけ)
  python install.py --check              何も書かずに、変わるファイルだけ表示する
  python install.py --tools codex,agy    道具を選ぶ(claude・codex・agy)
  python install.py --container-dir D:\\work   入れ物のフォルダを config.json に足す(繰り返せる)
  python install.py --uninstall          区画と hook の登録を外す(~/.handoff-hooks は残す)
"""
import argparse
import filecmp
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent
HOME = Path.home()
INSTALL_DIR = HOME / ".handoff-hooks"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
PYTHON = "python" if os.name == "nt" else "python3"

BEGIN = "<!-- handoff-hooks:begin(install.py が入れた区画。直すときは handoff-hooks の rules/handoff.md を直して配り直す) -->"
END = "<!-- handoff-hooks:end -->"
# 区画の探し方: 目印の行の先頭だけで探す(説明文は変えてよい)。古い名前の区画も入れ替える。
BLOCK_RE = re.compile(r"<!-- (?:claude-)?handoff-hooks:begin.*?<!-- (?:claude-)?handoff-hooks:end -->\n?", re.S)
OUR_SCRIPTS = ("handoff_bootstrap.py", "session_age_hint.py")
AGY_NAMES = ("handoff-hooks", "claude-handoff-hooks")

TOOLS = {
    "claude": {"dir": HOME / ".claude", "rules": HOME / ".claude" / "CLAUDE.md", "title": "~/.claude/CLAUDE.md"},
    "codex": {"dir": HOME / ".codex", "rules": HOME / ".codex" / "AGENTS.md", "title": "~/.codex/AGENTS.md"},
    "agy": {"dir": HOME / ".gemini", "rules": HOME / ".gemini" / "config" / "AGENTS.md", "title": "~/.gemini/config/AGENTS.md"},
}

changes = []  # (path, 説明)


def read_text(path):
    return path.read_bytes().decode("utf-8-sig") if path.exists() else None


def write_text(path, text, check):
    """改行は今のファイルに合わせる(新しいファイルは LF)。中身が同じなら書かない。"""
    old = read_text(path)
    newline = "\r\n" if old is not None and "\r\n" in old else "\n"
    data = text.replace("\r\n", "\n").replace("\n", newline)
    if old == data:
        return
    changes.append((path, "新規" if old is None else "更新"))
    if check:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if old is not None:
        shutil.copy2(path, path.with_name(f"{path.name}.bak-handoff-hooks-{STAMP}"))
    path.write_bytes(data.encode("utf-8"))


def copy_file(src, dst, check):
    if dst.exists() and filecmp.cmp(src, dst, shallow=False):
        return
    changes.append((dst, "新規" if not dst.exists() else "更新"))
    if not check:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def merge_rules(text, block, title):
    """区画を入れ替える。無ければ末尾に足す。block が None なら区画を外す。"""
    section = None if block is None else f"{BEGIN}\n{block.strip()}\n{END}\n"
    if text is None:
        return None if section is None else f"# 全体の指示({title})\n\n{section}"
    text = text.replace("\r\n", "\n")
    if BLOCK_RE.search(text):
        return BLOCK_RE.sub(lambda _: section or "", text, count=1).rstrip("\n") + "\n"
    if section is None:
        return text
    return text.rstrip("\n") + f"\n\n{section}"


def load_template(name):
    raw = (REPO / "config" / name).read_text(encoding="utf-8")
    hooks_dir = (INSTALL_DIR / "hooks").as_posix()
    # パスは空白があるときだけ引用符で囲む: agy は Windows で `cmd /c` に渡す途中で引用符が崩れ、python がファイルを開けない(2026-11 実測)。
    script = (lambda m: json.dumps(f'"{hooks_dir}/{m.group(1)}"')[1:-1]) if " " in hooks_dir else (lambda m: f"{hooks_dir}/{m.group(1)}")
    raw = re.sub(r"\{HOOKS\}/([A-Za-z_]+\.py)", script, raw)
    return json.loads(raw.replace("{PYTHON}", PYTHON))


def is_ours(group):
    """Claude Code・Codex の hook のまとまりのうち、このツールの物か(スクリプト名で見る。args に書く古い形も)。"""
    handlers = group.get("hooks", []) if isinstance(group, dict) else []

    def text(h):
        return " ".join([str(h.get("command", ""))] + [str(a) for a in h.get("args", [])])
    return any(any(s in text(h) for s in OUR_SCRIPTS) for h in handlers if isinstance(h, dict))


def merge_event_hooks(events, ours):
    """{イベント: [まとまり]} から自分の物を外し、ours(None なら外すだけ)を足す。"""
    for event in list(events):
        events[event] = [g for g in events[event] if not is_ours(g)]
        if not events[event]:
            del events[event]
    for event, groups in (ours or {}).items():
        events.setdefault(event, []).extend(groups)


def load_json(path):
    old = read_text(path)
    if not old:
        return {}
    try:
        data = json.loads(old)
    except ValueError:
        sys.exit(f"{path} が JSON として読めないので止めました(手で直してから、もう一度実行してください)")
    return data if isinstance(data, dict) else sys.exit(f"{path} の形が想定と違うので止めました")


def dump_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def merge_claude(uninstall, check):
    path = HOME / ".claude" / "settings.json"
    data = load_json(path)
    events = data.get("hooks", {})
    merge_event_hooks(events, None if uninstall else load_template("claude.hooks.json")["hooks"])
    if events:
        data["hooks"] = events
    else:
        data.pop("hooks", None)
    if data or path.exists():
        write_text(path, dump_json(data), check)


def merge_codex(uninstall, check):
    path = HOME / ".codex" / "hooks.json"
    if uninstall and not path.exists():
        return
    data = load_json(path)
    ours = load_template("codex.hooks.json")
    events = data.setdefault("hooks", {})
    merge_event_hooks(events, None if uninstall else ours["hooks"])
    desc = str(data.get("description", ""))
    if not desc or desc.startswith(("handoff-hooks:", "claude-handoff-hooks:")):
        if uninstall:
            data.pop("description", None)
        else:
            data["description"] = ours["description"]
    write_text(path, dump_json(data), check)


def merge_agy(uninstall, check):
    path = HOME / ".gemini" / "config" / "hooks.json"
    if uninstall and not path.exists():
        return
    data = load_json(path)
    for name in AGY_NAMES:
        data.pop(name, None)
    if not uninstall:
        data.update(load_template("agy.hooks.json"))
    write_text(path, dump_json(data), check)


def update_config(container_dirs, check):
    path = INSTALL_DIR / "config.json"
    old = read_text(path)
    config = json.loads(old) if old else json.loads((REPO / "config.example.json").read_text(encoding="utf-8"))
    for d in container_dirs:
        d = str(Path(d).expanduser().resolve())
        if d not in config.setdefault("container_dirs", []):
            config["container_dirs"].append(d)
    write_text(path, dump_json(config), check)


def main():
    ap = argparse.ArgumentParser(description="handoff-hooks を Claude Code・Codex・Antigravity へ入れる")
    ap.add_argument("--check", action="store_true", help="何も書かずに、変わるファイルだけ表示する")
    ap.add_argument("--tools", default="auto", help="claude,codex,agy のうち入れる物(既定: 設定フォルダがある物)")
    ap.add_argument("--container-dir", action="append", default=[], help="入れ物のフォルダ(配下をそれぞれ別のプロジェクトとする)")
    ap.add_argument("--uninstall", action="store_true", help="区画と hook の登録を外す")
    args = ap.parse_args()

    if args.tools == "auto":
        tools = [t for t, v in TOOLS.items() if v["dir"].exists()]
    else:
        tools = [t.strip() for t in args.tools.split(",") if t.strip()]
        unknown = set(tools) - set(TOOLS)
        if unknown:
            sys.exit(f"知らない道具: {', '.join(sorted(unknown))}(claude・codex・agy)")
    if not tools:
        sys.exit("入れる先がありません(~/.claude・~/.codex・~/.gemini のどれも無い)。--tools で選んでください")

    if not args.uninstall:
        for sub in ("hooks", "templates/handoff", "rules"):
            for src in sorted((REPO / sub).glob("*.*")):
                if src.suffix in (".py", ".md"):
                    copy_file(src, INSTALL_DIR / sub / src.name, args.check)
        update_config(args.container_dir, args.check)

    block = None if args.uninstall else (REPO / "rules" / "handoff.md").read_text(encoding="utf-8")
    for tool in tools:
        path = TOOLS[tool]["rules"]
        merged = merge_rules(read_text(path), block, TOOLS[tool]["title"])
        if merged is not None:
            write_text(path, merged, args.check)
        {"claude": merge_claude, "codex": merge_codex, "agy": merge_agy}[tool](args.uninstall, args.check)

    verb = "変わる予定" if args.check else "書いた"
    print(f"道具: {', '.join(tools)}")
    for path, kind in changes:
        print(f"{verb}({kind}): {path}")
    if not changes:
        print("変更なし")
    if "codex" in tools and not args.uninstall and any(p.name == "hooks.json" and ".codex" in p.parts for p, _ in changes):
        print("Codex: 新しい・変わった hook は許可するまで動きません。Codex アプリの「フックの確認」(設定 > Hooks)か CLI の /hooks で許可してください。")


if __name__ == "__main__":
    main()
