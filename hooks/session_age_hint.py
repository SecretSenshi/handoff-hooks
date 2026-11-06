"""UserPromptSubmit hook: in a long session, remind the model to update the handoff and suggest a fresh session for new work.

Reads the hook payload from stdin; prints nothing for short sessions (threshold: config.json `long_session_mb`).
`--tool codex|agy` switches the payload/output shape (default: Claude Code). For Antigravity it runs as PreInvocation,
which fires before every model call, so it only speaks on the first call of a turn (invocationNum 0).
`--user` (Stop hook) prints a message for the user instead of the model.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handoff_paths import TEMPLATE_DIR, TOOLS, context_output, handoff_paths, load_config, read_payload, tool_from_argv  # noqa: E402

tool = tool_from_argv(sys.argv)
payload = read_payload(sys.stdin.buffer.read(), tool)
if payload is None:
    sys.exit(0)
if tool == "agy" and payload.get("invocationNum", 0) != 0:
    sys.exit(0)
try:
    size = os.path.getsize(payload.get("transcript_path") or "")
except (OSError, TypeError):
    sys.exit(0)

config = load_config()
if size < float(config.get("long_session_mb", 5)) * 1024 * 1024:
    sys.exit(0)

name = TOOLS[tool]["name"]
rules = TOOLS[tool]["rules"]
mb = f"{size / 1024 / 1024:.0f}"

if "--user" in sys.argv:
    # Stop hook: shown to the user in the app, no model involved (Codex shows systemMessage as a warning).
    print(json.dumps({"systemMessage": (
        f"このセッションは約{mb}MBと長くなっています。"
        f"新しい機能や別の話題は、新しいセッションで始めると {name} の使用量を節約できます。"
    )}))
    sys.exit(0)

paths = handoff_paths(payload.get("cwd"), config)
if paths is None:
    handoff_rule = "このフォルダはプロジェクトのフォルダではないので、引継ぎ書は書かなくてよい。"
    switch_rule = "始める前に新しいセッションへの切り替えを勧めてください（新しいセッションでの最初の頼み方も1行で示す）。"
else:
    _, handoff, log = paths
    missing = "" if handoff.exists() else f"（まだ無いので、雛形 {TEMPLATE_DIR} から作る）"
    handoff_rule = (
        f"このターンでは、作業の続きであっても、このプロジェクトの引継ぎ書 {handoff}{missing} の【現在地】の"
        "自分の担当の小見出しが今の状態（進行中・ユーザー待ち・次の一手・未確認）を表しているか確かめ、"
        f"古ければ上書きし、経過ログ {log} へ追記してください（決まりは {rules}「引継ぎ書」。"
        "プロジェクトの CLAUDE.md・AGENTS.md に別の決まりがあればそちらが優先）。"
    )
    switch_rule = (
        "始める前に、上の引継ぎ書へ次のセッションが読む入口を書いてから、新しいセッションへの切り替えを勧めてください"
        "（新しいセッションでの最初の頼み方も1行で示す）。"
    )

note = (
    f"[長いセッション] このセッションの記録は約{mb}MBあり、文脈が大きいため、"
    f"道具を1回使うたびに {name} の使用量を多く消費します。"
    + handoff_rule
    + "今回のユーザーの依頼が、新しい機能の追加・別の話題など、このセッションの続きでない作業なら、"
    + switch_rule
    + "短い質問、今の作業の続き・修正・確認なら、切り替えは勧めずにそのまま進めてください。"
)
print(json.dumps(context_output(tool, "UserPromptSubmit", note)))
