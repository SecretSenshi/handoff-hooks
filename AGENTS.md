# handoff-hooks で作業するときの決まり

- 公開リポジトリ。個人のパス・ユーザー名・プロジェクト名・メールアドレス・秘密を入れない。引継ぎ書(`handoff/`)は `.gitignore` で入れない。
- 決まりの原本は `rules/handoff.md`、hook の登録の原本は `config/*.hooks.json`。各道具の実物(`~/.claude`・`~/.codex`・`~/.gemini/config`・`~/.handoff-hooks`)は写しなので、原本を直して `python install.py` で配る。
- 道具ごとの違い(入力・出力の形と決まりの置き場)は `hooks/handoff_paths.py` の `TOOLS`・`read_payload`・`context_output` に集める。
- 変えたら `python tests/test_hooks.py` を通してから `python install.py --check` → `python install.py`。Codex の hook のコマンドを変えたら、Codex で許可し直す。
- hook の出力は `json.dumps` の ASCII のエスケープのまま(Windows の python の標準出力は cp932 などのことがある)。
