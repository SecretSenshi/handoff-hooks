# handoff-hooks

AI のコーディングエージェント(**Claude Code・Codex・Antigravity**)に、どのプロジェクトでも同じ形の「引継ぎ書」を書かせるための hook・雛形・決まりです。セッションが変わっても、モデルや道具を替えても、次の担当が `handoff/ORCHESTRATOR-HANDOFF.md` の【現在地】を読めば続きから始められます。

> **English summary**: Hooks, templates and global rules that make Claude Code, OpenAI Codex and Google Antigravity keep a per-project handoff document (`handoff/ORCHESTRATOR-HANDOFF.md` + monthly append-only log). On session start the agent is told where the handoff is (or to create it from the template on its first working turn); in long sessions it is reminded to update it. Messages and templates are in Japanese. Install with `python install.py`.

## 何をするか

- **起動時**: そのフォルダのプロジェクトに引継ぎ書があれば「【現在地】を読んでから始める」、無ければ「最初に作業したターンで雛形から作る」とモデルに伝えます(hook はファイルを作りません。調べものだけのフォルダに空の引継ぎ書を散らさないため)。
- **毎ターン**: 作業したターンの中で、本体の【現在地】と経過ログの両方へ記録させます(全体の決まり)。
- **長いセッション**: 記録が一定の大きさ(既定 5MB)を超えたら、引継ぎ書を最新にさせ、別の作業なら新しいセッションを勧めさせます。

引継ぎ書の形:

```
<プロジェクト>/handoff/
  ORCHESTRATOR-HANDOFF.md     本体。冒頭の【現在地】に作業ごとの小見出し(状態・次の一手・ユーザー待ち・未確認・道具の場所)
  log/ORCH-LOG-YYYY-MM.md     経過ログ。1 ターン 1 項目で追記だけ
```

プロジェクトのフォルダは、起動したフォルダから上へたどって最初に `.git`・`CLAUDE.md`・`AGENTS.md`・`GEMINI.md`・`handoff/ORCHESTRATOR-HANDOFF.md` のどれかがあるフォルダです。ホーム・ダウンロード等・ドライブの直下では作りません。

## 入れ方

Python 3.8 以上が要ります。

```bash
git clone https://github.com/SecretSenshi/handoff-hooks.git
cd handoff-hooks
python tests/test_hooks.py      # 動作の確認(本物のホームには書かない)
python install.py --check       # 何が変わるかだけ見る
python install.py               # 入れる
```

- 入れる先は、`~/.claude`・`~/.codex`・`~/.gemini` のうちあるものだけです(`--tools claude,codex,agy` で選べます)。
- 変えるファイルは、変える前に `<名前>.bak-handoff-hooks-<日時>` として同じフォルダに残します。他の hook・設定・指示の文は残します。
- **Codex は、新しい・変わった hook を許可するまで動かしません**(通知が出ないこともあります)。入れた後に、Codex アプリの「フックの確認」(設定 > Hooks)か、CLI の `/hooks` で許可してください。
- 外すとき: `python install.py --uninstall`(決まりの区画と hook の登録を外します。`~/.handoff-hooks` は残ります)。

## 入る場所

| | 全体の決まり(区画を足す) | hook の登録 | hook の入力 → 出力 |
|---|---|---|---|
| Claude Code | `~/.claude/CLAUDE.md` | `~/.claude/settings.json` | `cwd`・`transcript_path` → `hookSpecificOutput.additionalContext` |
| Codex | `~/.codex/AGENTS.md` | `~/.codex/hooks.json` | Claude Code と同じ形(要・許可) |
| Antigravity | `~/.gemini/config/AGENTS.md` | `~/.gemini/config/hooks.json` | `workspacePaths`・`transcriptPath` → `injectSteps[].systemMessage` |

hook・雛形・設定の実物は `~/.handoff-hooks/` の1組を3つの道具で共用します。

## 設定(`~/.handoff-hooks/config.json`)

```json
{
  "container_dirs": [],
  "long_session_mb": 5
}
```

- `container_dirs`: 中にプロジェクトを並べて置くだけの「入れ物」のフォルダ。配下のフォルダはそれぞれ別のプロジェクトとして扱い、入れ物の引継ぎ書へ寄せません(入れ物そのもので起動したときだけ、入れ物を1つのプロジェクトとします)。`python install.py --container-dir D:\work` でも足せます。
- `long_session_mb`: 長いセッションの通知を出す記録の大きさ。

## 中身

| ファイル | 役目 |
|---|---|
| `rules/handoff.md` | 全体の決まり「引継ぎ書」。各道具の全体の指示ファイルへ、目印の行で囲んだ区画として入る |
| `hooks/handoff_paths.py` | プロジェクトのフォルダと引継ぎ書の場所の決め方。道具ごとの入力・出力の形の違い |
| `hooks/handoff_bootstrap.py` | 起動時(SessionStart)の案内 |
| `hooks/session_age_hint.py` | 長いセッションの通知(Claude Code・Codex は UserPromptSubmit と Stop、Antigravity は PreInvocation の各ターン最初の1回) |
| `templates/handoff/` | 本体と経過ログの雛形 |
| `config/*.hooks.json` | 各道具へ登録する hook(`{PYTHON}`・`{HOOKS}` は install.py が置き換える) |
| `install.py` | 入れる・確かめる・外す |
| `tests/test_hooks.py` | 3つの道具の入力の形で hook を動かし、仮のホームで install.py を通す |

## 注意

- 決まりと案内は日本語です。
- hook の出力は ASCII のエスケープ(`\uXXXX`)の JSON です。Windows の python の標準出力が cp932 などでも化けません。
- Antigravity は CLI(`agy`)で確かめています。アプリ版・IDE でも同じ `~/.gemini/config` を読むはずですが、確かめていません。
- プロジェクトの CLAUDE.md・AGENTS.md・GEMINI.md に引継ぎについての決まりがあれば、そちらが優先されるように書いてあります。

## License

MIT
