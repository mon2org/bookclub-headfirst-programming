#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """git コマンドを実行して結果を返す。"""
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def branch_exists_local(repo_root: Path, branch: str) -> bool:
    """ローカルブランチの存在を判定する。"""
    result = git("show-ref", "--verify", f"refs/heads/{branch}", cwd=repo_root, check=False)
    return result.returncode == 0


def branch_exists_remote(repo_root: Path, remote: str, branch: str) -> bool:
    """リモートブランチの存在を判定する。"""
    result = git("ls-remote", "--heads", remote, branch, cwd=repo_root, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def next_session_number(sessions_root: Path) -> str:
    """sessions 配下から次のセッション番号を算出する。"""
    max_value = 0
    for child in sessions_root.iterdir():
        if child.is_dir() and re.fullmatch(r"\d+", child.name):
            max_value = max(max_value, int(child.name))
    return f"{max_value + 1:03d}"


def ensure_clean(repo_root: Path) -> None:
    """作業ツリーがクリーンかを検証する。"""
    status = git("status", "--porcelain", cwd=repo_root)
    if status.stdout.strip():
        raise SystemExit("作業ツリーに未コミット変更があります。コミットまたは退避してから再実行してください。")


def main() -> None:
    """セッション用ブランチを作成して push する。"""
    parser = argparse.ArgumentParser(description="セッション用ブランチを作成して push する")
    parser.add_argument("--base", default="main", help="ベースブランチ（既定: main）")
    parser.add_argument("--remote", default="origin", help="push 先リモート（既定: origin）")
    parser.add_argument("--prefix", default="session", help="ブランチ接頭辞（既定: session）")
    parser.add_argument("--session", default="", help="セッション番号（例: 004）。未指定時は自動採番")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    sessions_root = repo_root / "sessions"
    if not sessions_root.exists():
        raise SystemExit("sessions ディレクトリが見つかりません。")

    ensure_clean(repo_root)

    session = args.session or next_session_number(sessions_root)
    branch = f"{args.prefix}/{session}"

    print(f"取得中: {args.remote}/{args.base}")
    git("fetch", args.remote, args.base, cwd=repo_root)

    print(f"ベースブランチへ切替: {args.base}")
    git("switch", args.base, cwd=repo_root)
    git("merge", "--ff-only", f"{args.remote}/{args.base}", cwd=repo_root)

    if branch_exists_local(repo_root, branch):
        raise SystemExit(f"ローカルに既存ブランチがあります: {branch}")
    if branch_exists_remote(repo_root, args.remote, branch):
        raise SystemExit(f"リモートに既存ブランチがあります: {args.remote}/{branch}")

    print(f"ブランチ作成: {branch}")
    git("switch", "-c", branch, cwd=repo_root)

    print(f"ブランチを push: {args.remote}/{branch}")
    git("push", "-u", args.remote, branch, cwd=repo_root)

    print(f"セッションブランチの作成と push が完了: {branch}")


if __name__ == "__main__":
    main()