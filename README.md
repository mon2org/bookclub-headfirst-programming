---
book:
  title: "Head First はじめてのプログラミング"
---

# bookclub-headfirst-programming
『Head First はじめてのプログラミング ―頭とからだで覚えるPythonプログラミング入門』(オライリー・ジャパン,2019)読書会のためのリポジトリ

## 準備
```bash
curl https://raw.githubusercontent.com/mon2org/bookclub-headfirst-programming/refs/heads/main/scripts/setup.sh | bash
```

## セッションファイル仕様
- `sessions` ディレクトリ配下には、0埋め10進数3桁のディレクトリ（例: `001`, `002`）を作成する。
- セッションごとに `git` ユーザー名をファイル名として、`*.ipynb` と `*.md` を同じ階層に作成する。
- `ipynb` の先頭見出しは `# 第N回` とする。
- `md` の形式は次のとおりとする。

```markdown
---
created: YYYY-MM-DD[T]HH:mm:ss
updated: YYYY-MM-DD[T]HH:mm:ss
---
[Google Colab](URL)
```

※ Google Colab のリンクは、ブランチ名をURLエンコードした実行可能な形式で生成する。

## 主要タスク
- セッション開始（作成+ブランチ作成を連続実行）: `mise run start-session`
- セッションファイル作成: `mise run create-session`
- セッションブランチ作成: `mise run create-session-branch`
- upstream -> fork 同期: `mise run sync-fork`
- PR が upstream にマージされた後の fork/main 更新も同じ: `mise run sync-fork`

## 運用メモ
- `start-session` は同じセッション番号を明示的に `create_session_branch.py` と `create_session_files.py` の両方へ渡して実行する。
- これにより、番号のズレや実行順依存を防ぐ。

## GitHub Actions（手動実行）
- ワークフロー: `.github/workflows/start-session.yml`
- トリガー: `workflow_dispatch`（手動実行）
- 実行内容: GitHub Actions 上で `mise run start-session -- --session XXX` を実行する。
- `session` 未指定時は `sessions/*` から次番号を自動採番する。
- 指定または採番した `sessions/XXX` が既に存在する場合は作成せずにスキップする。

### 実行手順
1. GitHub の `Actions` タブを開く。
2. `セッション開始` ワークフローを選ぶ。
3. 必要なら `session` に番号（例: `007`）を入力する。
4. `Run workflow` を押して手動実行する。

### 注意
- ワークフローは `permissions: contents: write` を使用する。
- リポジトリ設定で Actions の権限が `Read and write permissions` になっていることを確認する。