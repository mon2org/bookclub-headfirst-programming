#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


def run_git(*args: str) -> str:
    """git コマンドを実行して標準出力を返す。"""
    result = subprocess.run(
        ["git", *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout.strip()


def sanitize_filename(name: str) -> str:
    """ファイル名として安全な文字列に整形する。"""
    sanitized = re.sub(r"[^A-Za-z0-9._-]", "_", name.strip())
    return sanitized.strip("._") or "user"


def resolve_github_username_from_env() -> str:
    """CI や Codespaces の環境変数からユーザー名を解決する。"""
    is_codespaces = bool(os.environ.get("CODESPACES") or os.environ.get("CODESPACE_NAME"))
    is_github_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"

    if not (is_codespaces or is_github_actions):
        return ""

    for key in ("GITHUB_ACTOR", "GITHUB_USER", "GIT_COMMITTER_NAME"):
        value = os.environ.get(key, "").strip()
        if value:
            return sanitize_filename(value)

    return ""


def resolve_git_username() -> str:
    """git 設定や環境変数からユーザー名を取得する。"""
    github_name = resolve_github_username_from_env()
    if github_name:
        return github_name

    name = run_git("config", "user.name")
    if name:
        return sanitize_filename(name)

    email = run_git("config", "user.email")
    if email and "@" in email:
        local = email.split("@", 1)[0]
        return sanitize_filename(local)

    raise SystemExit(
        "ユーザー情報が見つかりません。"
        "Codespaces / GitHub Actions では GITHUB_ACTOR または GITHUB_USER、"
        "それ以外では git config user.name（または git config user.email）を設定してから再実行してください。"
    )


def resolve_repo_info() -> tuple[str, str, str]:
    """origin から owner/repo/branch を解決する。"""
    remote = run_git("remote", "get-url", "origin")
    owner = ""
    repo = ""
    if remote:
        match_https = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$", remote)
        if match_https:
            owner = match_https.group("owner")
            repo = match_https.group("repo")

    branch = run_git("rev-parse", "--abbrev-ref", "HEAD") or "main"
    return owner, repo, branch


def normalize_session_name(value: str) -> str:
    """セッション番号を3桁ゼロ埋め文字列へ正規化する。"""
    if not value.isdigit():
        raise SystemExit("--session には数字のみを指定してください。例: 001")

    session_number = int(value)
    if session_number <= 0:
        raise SystemExit("--session には 1 以上の数値を指定してください。")
    return f"{session_number:03d}"


def next_session_name(sessions_root: Path) -> str:
    """次に作成すべきセッション番号を返す。"""
    sessions_root.mkdir(parents=True, exist_ok=True)

    max_value = 0
    for child in sessions_root.iterdir():
        if child.is_dir() and child.name.isdigit():
            max_value = max(max_value, int(child.name))

    next_value = max_value + 1
    return f"{next_value:03d}"


def create_session_dir(sessions_root: Path, session_name: str) -> Path:
    """指定したセッション番号のディレクトリを作成する。"""
    next_name = normalize_session_name(session_name)
    target = sessions_root / next_name
    if target.exists():
        raise SystemExit(f"既存ディレクトリがあります: {target}")
    target.mkdir(parents=True, exist_ok=False)
    return target


def next_session_dir(sessions_root: Path) -> Path:
    """次のセッションディレクトリを自動作成する。"""
    return create_session_dir(sessions_root, next_session_name(sessions_root))


def build_notebook_json(session_number: int) -> dict:
    """セッション用ノートブック JSON を構築する。"""
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {"language": "markdown"},
                "source": [
                    f"# 第{session_number}回\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {"language": "python"},
                "outputs": [],
                "source": [
                    "# ここからコードを書く\n",
                ],
            },
        ],
        "metadata": {
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main() -> None:
    """セッション用 ipynb と md ファイルを生成する。"""
    parser = argparse.ArgumentParser(description="セッション用ファイルを作成する")
    parser.add_argument("--session", default="", help="作成するセッション番号（例: 001）。未指定時は次番号を自動採番")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    sessions_root = repo_root / "sessions"

    user_name = resolve_git_username()
    session_dir = create_session_dir(sessions_root, args.session) if args.session else next_session_dir(sessions_root)

    notebook_path = session_dir / f"{user_name}.ipynb"
    markdown_path = session_dir / f"{user_name}.md"

    session_number = int(session_dir.name)
    notebook = build_notebook_json(session_number)
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    owner, repo, branch = resolve_repo_info()
    if owner and repo:
        rel_path = notebook_path.relative_to(repo_root).as_posix()
        encoded_branch = quote(branch, safe="")
        encoded_path = quote(rel_path, safe="/")
        colab_url = f"https://colab.research.google.com/github/{owner}/{repo}/blob/{encoded_branch}/{encoded_path}"
    else:
        colab_url = "URL"

    markdown = (
        "---\n"
        f"created: {now}\n"
        f"updated: {now}\n"
        "---\n"
        f"[Google Colab]({colab_url})\n"
    )
    markdown_path.write_text(markdown, encoding="utf-8")

    print(f"作成したディレクトリ: {session_dir}")
    print(f"作成したノートブック: {notebook_path.name}")
    print(f"作成したMarkdown: {markdown_path.name}")


if __name__ == "__main__":
    main()
