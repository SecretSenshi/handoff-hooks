"""SessionStart hook: そのプロジェクトの引継ぎ書の場所を伝える。無ければ作るよう伝える。

`--tool codex|agy` で入力と出力の形を切り替える(無ければ Claude Code)。
ファイルはこの hook では作らない: 起動しただけで作業しないフォルダ(調べものだけ等)に空の引継ぎ書を散らさないため、
最初に作業したターンでモデルが雛形から作る(全体の決まり「引継ぎ書」= rules/handoff.md)。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from handoff_paths import TEMPLATE_DIR, TOOLS, context_output, handoff_paths, read_payload, tool_from_argv  # noqa: E402

tool = tool_from_argv(sys.argv)
payload = read_payload(sys.stdin.buffer.read(), tool)
if payload is None:
    sys.exit(0)

paths = handoff_paths(payload.get("cwd"))
if paths is None:
    sys.exit(0)
root, handoff, log = paths
rules = TOOLS[tool]["rules"]

if handoff.exists():
    note = (
        f"[引継ぎ書] このプロジェクト({root})の引継ぎ書は {handoff}、今月の経過ログは {log}。"
        "作業を始める前に、引継ぎ書の冒頭の【現在地】を読んでください。"
        f"作業(ファイルの変更・コマンド・調べもの)をしたターンでは、そのターンの中で両方に記録してください(決まりは {rules}「引継ぎ書」)。"
    )
else:
    note = (
        f"[引継ぎ書] このプロジェクト({root})にはまだ引継ぎ書がありません。"
        f"最初に作業(ファイルの変更・コマンド・調べもの)をしたターンで、雛形 {TEMPLATE_DIR} から {handoff} と {log} を作り、"
        f"そのターンの記録を書いてください(ユーザーへの確認は要らない。決まりは {rules}「引継ぎ書」)。"
        "既に別の形の引継ぎ文書があれば、消さずに本体の【常設】からリンクしてください。"
    )
# ensure_ascii のまま出す: Windows の python の標準出力は cp932 などのことがあり、日本語をそのまま出すと化ける。
print(json.dumps(context_output(tool, "SessionStart", note)))
