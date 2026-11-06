"""hook を3つの道具(Claude Code・Codex・Antigravity)の入力の形で動かし、出力を確かめる。
install.py を仮のホームへ入れ・入れ直し・外して、他の設定が残ることも確かめる。

使い方: python tests/test_hooks.py(このリポジトリの hooks/ を使う。本物のホームには書かない)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / "hooks"
sys.path.insert(0, str(REPO))
import install  # noqa: E402

failures = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f": {detail}"))
    if not cond:
        failures.append(name)


def run(script, payload, *args, env=None):
    p = subprocess.run(
        [sys.executable, str(HOOKS / script), *args],
        input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=30, env=env,
    )
    out = p.stdout.decode("ascii")  # ASCII のエスケープで出ていること(日本語がそのまま出ると cp932 で化ける)
    return p.returncode, (json.loads(out) if out.strip() else None)


def payload_for(tool, cwd, transcript=None, **extra):
    if tool == "agy":
        return {"workspacePaths": [str(cwd).replace("\\", "/")], "transcriptPath": transcript, "conversationId": "t", **extra}
    return {"cwd": str(cwd), "transcript_path": transcript, "session_id": "t", **extra}


def context_of(tool, out):
    if tool == "agy":
        return out["injectSteps"][0]["systemMessage"]["systemMessage"]
    return out["hookSpecificOutput"]["additionalContext"]


# 既定の一時フォルダは AppData の下(Windows)で、プロジェクトとみなさない決まりなので、このフォルダの中に作る。
with tempfile.TemporaryDirectory(dir=Path(__file__).parent, prefix="_tmp-") as tmp:
    tmp = Path(tmp)
    project = tmp / "project"
    (project / "handoff").mkdir(parents=True)
    (project / "handoff" / "ORCHESTRATOR-HANDOFF.md").write_text("x", encoding="utf-8")
    fresh = tmp / "fresh-project"
    (fresh / ".git").mkdir(parents=True)
    container = tmp / "container"
    (container / ".git").mkdir(parents=True)  # 入れ物に印があっても、配下はそれぞれ別のプロジェクト
    (container / "child" / "sub").mkdir(parents=True)
    small = tmp / "small.jsonl"
    small.write_bytes(b"{}\n")
    big = tmp / "big.jsonl"
    with open(big, "wb") as f:
        f.truncate(6 * 1024 * 1024)
    config = tmp / "config.json"
    config.write_text(json.dumps({"container_dirs": [str(container)], "long_session_mb": 5}), encoding="utf-8")
    env = dict(os.environ, HANDOFF_HOOKS_CONFIG=str(config))

    for tool in ("claude", "codex", "agy"):
        args = ["--tool", tool]
        rules = {"claude": "~/.claude/CLAUDE.md", "codex": "~/.codex/AGENTS.md", "agy": "~/.gemini/config/AGENTS.md"}[tool]

        rc, out = run("handoff_bootstrap.py", payload_for(tool, project / "handoff"), *args, env=env)
        ctx = context_of(tool, out) if out else ""
        check(f"{tool}: 起動時・引継ぎ書あり", rc == 0 and str(project) in ctx and "【現在地】" in ctx and rules in ctx, out)
        if tool != "agy":
            check(f"{tool}: hookEventName", out["hookSpecificOutput"]["hookEventName"] == "SessionStart", out)

        rc, out = run("handoff_bootstrap.py", payload_for(tool, fresh), *args, env=env)
        ctx = context_of(tool, out) if out else ""
        check(f"{tool}: 起動時・引継ぎ書なし", rc == 0 and "まだ引継ぎ書がありません" in ctx and str(fresh) in ctx, out)

        rc, out = run("handoff_bootstrap.py", payload_for(tool, container / "child" / "sub"), *args, env=env)
        ctx = context_of(tool, out) if out else ""
        check(f"{tool}: 入れ物の配下は入れ物へ寄せない", rc == 0 and str(container / "child" / "sub" / "handoff") in ctx, out)

        rc, out = run("handoff_bootstrap.py", payload_for(tool, Path.home()), *args, env=env)
        check(f"{tool}: ホームでは黙る", rc == 0 and out is None, out)

        rc, out = run("handoff_bootstrap.py", {}, *args, env=env)
        check(f"{tool}: 場所の無い入力では黙る", rc == 0 and out is None, out)

        extra = {"invocationNum": 0} if tool == "agy" else {"prompt": "x"}
        rc, out = run("session_age_hint.py", payload_for(tool, fresh, str(small), **extra), *args, env=env)
        check(f"{tool}: 短いセッションは黙る", rc == 0 and out is None, out)

        rc, out = run("session_age_hint.py", payload_for(tool, fresh, str(big), **extra), *args, env=env)
        ctx = context_of(tool, out) if out else ""
        check(f"{tool}: 長いセッションの通知", rc == 0 and "[長いセッション]" in ctx and rules in ctx, out)
        if tool != "agy":
            check(f"{tool}: 通知の hookEventName", out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit", out)
            rc, out = run("session_age_hint.py", payload_for(tool, fresh, str(big)), *args, "--user", env=env)
            check(f"{tool}: Stop はユーザーへの表示", rc == 0 and "systemMessage" in out, out)
        else:
            rc, out = run("session_age_hint.py", payload_for(tool, fresh, str(big), invocationNum=2), *args, env=env)
            check("agy: 同じターンの2回目以降は黙る", rc == 0 and out is None, out)

    # install.py を仮のホームで通す(Windows は USERPROFILE、それ以外は HOME がホーム)。
    home = tmp / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text(json.dumps({
        "theme": "dark",
        "hooks": {
            "SessionStart": [{"hooks": [{"type": "command", "command": "python", "args": ["C:/old/.claude/hooks/handoff_bootstrap.py"]}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "other-hook"}]}],
        },
    }, indent=2), encoding="utf-8")
    (home / ".codex").mkdir()
    (home / ".codex" / "AGENTS.md").write_text("自分の決まり\n", encoding="utf-8")
    (home / ".gemini" / "config").mkdir(parents=True)
    (home / ".gemini" / "config" / "hooks.json").write_text(json.dumps({"mine": {"Stop": []}, "claude-handoff-hooks": {}}), encoding="utf-8")
    henv = dict(os.environ, USERPROFILE=str(home), HOME=str(home))

    def inst(*a):
        p = subprocess.run([sys.executable, str(REPO / "install.py"), *a], capture_output=True, env=henv, timeout=60)
        return p.returncode, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace")

    rc, out = inst("--container-dir", str(container))
    check("install: 動く", rc == 0, out)
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    starts = settings["hooks"]["SessionStart"]
    check("install: Claude の古い登録を入れ替える", len(starts) == 1 and ".handoff-hooks/hooks/handoff_bootstrap.py" in starts[0]["hooks"][0]["command"], starts)
    check("install: Claude の他の hook・設定は残る", settings["theme"] == "dark" and settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "other-hook", settings)
    agents = (home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    check("install: Codex の決まりは他の文の後ろに区画", agents.startswith("自分の決まり\n") and install.BEGIN in agents and install.END in agents, agents[:200])
    codex_hooks = json.loads((home / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    check("install: Codex の hook", set(codex_hooks["hooks"]) == {"SessionStart", "UserPromptSubmit", "Stop"}, codex_hooks)
    agy_hooks = json.loads((home / ".gemini" / "config" / "hooks.json").read_text(encoding="utf-8"))
    check("install: agy の hook(古い名前は外し、他は残す)", set(agy_hooks) == {"mine", "handoff-hooks"}, agy_hooks)
    check("install: agy の決まり", install.BEGIN in (home / ".gemini" / "config" / "AGENTS.md").read_text(encoding="utf-8"))
    conf = json.loads((home / ".handoff-hooks" / "config.json").read_text(encoding="utf-8"))
    check("install: config.json に入れ物", str(container.resolve()) in conf["container_dirs"], conf)
    check("install: hook と雛形を写す", (home / ".handoff-hooks" / "hooks" / "handoff_paths.py").exists() and (home / ".handoff-hooks" / "templates" / "handoff" / "ORCHESTRATOR-HANDOFF.md").exists())
    check("install: 変える前の写しを残す", any(p.name.startswith("settings.json.bak-handoff-hooks-") for p in (home / ".claude").iterdir()))

    if os.name == "nt":
        # agy は Windows で登録したコマンドを `cmd /c <コマンド>` で動かす。文字列のまま渡して同じ形で試す。
        cmd = agy_hooks["handoff-hooks"]["SessionStart"][0]["command"]
        p = subprocess.run("cmd /c " + cmd, input=json.dumps(payload_for("agy", fresh)).encode(), capture_output=True, env=dict(env, **{"USERPROFILE": str(home)}), timeout=30)
        check("install: agy のコマンドが cmd /c で動く", p.returncode == 0 and b"injectSteps" in p.stdout, p.stderr[:300])

    rc, out = inst("--check")
    check("install: 2回目は変更なし", rc == 0 and "変更なし" in out, out)

    rc, out = inst("--uninstall")
    settings = json.loads((home / ".claude" / "settings.json").read_text(encoding="utf-8"))
    check("uninstall: Claude は自分の登録だけ外す", rc == 0 and "SessionStart" not in settings["hooks"] and "PreToolUse" in settings["hooks"], settings)
    agents = (home / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
    check("uninstall: Codex の区画を外し、他の文は残す", agents == "自分の決まり\n", repr(agents))
    agy_hooks = json.loads((home / ".gemini" / "config" / "hooks.json").read_text(encoding="utf-8"))
    check("uninstall: agy は自分の hook だけ外す", set(agy_hooks) == {"mine"}, agy_hooks)

# 区画の入れ替え(古い名前の区画も入れ替える)
block = "## 引継ぎ書(handoff)\n\n- 新しい決まり\n"
old = "前書き\n\n<!-- claude-handoff-hooks:begin(古い説明) -->\n## 古い節\n<!-- claude-handoff-hooks:end -->\n\n後書き\n"
merged = install.merge_rules(old, block, "t")
check("rules: 古い名前の区画を入れ替える", "古い節" not in merged and "新しい決まり" in merged and "前書き" in merged and "後書き" in merged, merged)
check("rules: 2回目は変わらない", install.merge_rules(merged, block, "t") == merged)

print(f"\n{'失敗 ' + str(len(failures)) + ' 件' if failures else 'すべて通った'}")
sys.exit(1 if failures else 0)
