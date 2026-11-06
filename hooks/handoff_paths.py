"""実行したフォルダから、そのプロジェクトの引継ぎ書(handoff)の場所を決める共通の処理。

handoff_bootstrap.py(起動時の案内)と session_age_hint.py(長いセッションの通知)が使う。
規則は rules/handoff.md(install.py が各道具の全体の指示ファイルへ写す)と同じにしておくこと。片方だけ変えると、案内と決まりが食い違う。
道具(Claude Code・Codex・Antigravity)ごとの違いは、入力と出力の形と、全体の決まりの置き場だけで、ここに集める。
"""
import json
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # インストール先(~/.handoff-hooks)またはリポジトリ
TEMPLATE_DIR = BASE_DIR / "templates" / "handoff"
CONFIG_PATH = Path(os.environ.get("HANDOFF_HOOKS_CONFIG") or BASE_DIR / "config.json")

# 上へたどったとき、ここにあればプロジェクトのフォルダとみなす印。
# .claude・.codex は入れない: 入れ物のフォルダ自体に置かれていることがあり、入れると配下の全部がそこの引継ぎ書へ寄ってしまう。
MARKERS = (".git", "CLAUDE.md", "AGENTS.md", "GEMINI.md", os.path.join("handoff", "ORCHESTRATOR-HANDOFF.md"))

# ホーム直下の置き場そのものはプロジェクトではない(中に作ったフォルダは扱う)。
HOME_PLAIN_DIRS = ("downloads", "desktop", "documents", "pictures", "videos", "music", "onedrive", ".claude", ".codex", ".gemini")

TOOLS = {
    "claude": {"name": "Claude", "rules": "~/.claude/CLAUDE.md"},
    "codex": {"name": "Codex", "rules": "~/.codex/AGENTS.md"},
    "agy": {"name": "Antigravity", "rules": "~/.gemini/config/AGENTS.md"},
}


def load_config():
    """~/.handoff-hooks/config.json。無い・読めないときは既定値。"""
    config = {"container_dirs": [], "long_session_mb": 5}
    try:
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError):
        pass
    return config


def _same(a, b):
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def project_root(cwd, config=None):
    """プロジェクトのフォルダを返す。引継ぎ書を作らない場所(ホーム・ドライブの直下・AppData)なら None。"""
    if not cwd:
        return None
    config = config or load_config()
    start = Path(cwd).resolve()
    home = Path.home().resolve()
    if _same(start, home) or start.parent == start or "AppData" in start.parts:
        return None
    if _same(start.parent, home) and start.name.lower() in HOME_PLAIN_DIRS:
        return None
    # 入れ物のフォルダ(中にプロジェクトを並べて置くだけの所。config.json の container_dirs)は、
    # 配下から上へたどるときはそこで止め、入れ物の引継ぎ書へ寄せない。入れ物そのもので起動したときだけ1つのプロジェクトとする。
    containers = [Path(os.path.expanduser(c)) for c in config.get("container_dirs", [])]
    for d in [start, *start.parents]:
        if _same(d, home) or d.parent == d:
            break
        if any(_same(d, c) for c in containers) and not _same(d, start):
            break
        if any((d / m).exists() for m in MARKERS):
            return d
    return start


def handoff_paths(cwd, config=None):
    """(プロジェクトのフォルダ, 本体のパス, 今月の経過ログのパス) を返す。プロジェクトでなければ None。"""
    root = project_root(cwd, config)
    if root is None:
        return None
    month = datetime.now().astimezone().strftime("%Y-%m")
    return root, root / "handoff" / "ORCHESTRATOR-HANDOFF.md", root / "handoff" / "log" / f"ORCH-LOG-{month}.md"


def tool_from_argv(argv):
    """--tool claude|codex|agy(無ければ claude)。"""
    if "--tool" in argv:
        i = argv.index("--tool")
        if i + 1 < len(argv) and argv[i + 1] in TOOLS:
            return argv[i + 1]
    return "claude"


def read_payload(stdin_bytes, tool):
    """hook の入力を {"cwd", "transcript_path", ...元の項目} にそろえる。読めなければ None。

    Claude Code と Codex は cwd・transcript_path(snake_case)、Antigravity は workspacePaths・transcriptPath(camelCase)。
    """
    try:
        payload = json.loads(stdin_bytes.decode("utf-8-sig"))
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    if tool == "agy":
        workspaces = payload.get("workspacePaths") or []
        payload.setdefault("cwd", workspaces[0] if workspaces else None)
        payload.setdefault("transcript_path", payload.get("transcriptPath"))
    return payload


def context_output(tool, event, note):
    """モデルに渡す追加の文脈を、その道具の hook の出力の形にする。"""
    if tool == "agy":
        return {"injectSteps": [{"systemMessage": {"systemMessage": note}}]}
    # Claude Code と Codex は同じ形(Codex は Claude Code の hook と互換)。
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": note}}
