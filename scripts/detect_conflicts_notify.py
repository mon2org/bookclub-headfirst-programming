#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
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


def current_branch(repo_root: Path) -> str:
    """現在のブランチ名を返す。"""
    result = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    return result.stdout.strip()


def list_conflicted_files(worktree: Path) -> list[str]:
    """衝突中ファイル一覧を返す。"""
    result = git("diff", "--name-only", "--diff-filter=U", cwd=worktree)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def notify(message: str, is_error: bool) -> None:
    """実行環境に応じた通知を出力する。"""
    in_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    if in_actions and is_error:
        print(f"::error title=マージコンフリクト検出::{message}")
    elif in_actions:
        print(f"::notice title=コンフリクト確認::{message}")
    else:
        level = "エラー" if is_error else "OK"
        print(f"[{level}] {message}")


def main() -> None:
    """指定 ref 間のマージ衝突有無を検出して通知する。"""
    parser = argparse.ArgumentParser(description="指定した基準 ref とのマージコンフリクトを検出する")
    parser.add_argument("--base", default="upstream/main", help="マージ元にする基準 ref")
    parser.add_argument("--head", default="", help="検査対象の head ref（既定: 現在ブランチ）")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    head_ref = args.head or current_branch(repo_root)

    print(f"コンフリクト検査に必要な ref を取得中（base: {args.base}, head: {head_ref}）")
    git("fetch", "--all", "--prune", cwd=repo_root)

    tmpdir = Path(tempfile.mkdtemp(prefix="conflict-check-"))
    try:
        git("worktree", "add", "--detach", str(tmpdir), head_ref, cwd=repo_root)
        merge_result = git("merge", "--no-commit", "--no-ff", args.base, cwd=tmpdir, check=False)

        conflicted = list_conflicted_files(tmpdir)
        has_conflict = bool(conflicted) or merge_result.returncode != 0

        if has_conflict:
            files = ", ".join(conflicted) if conflicted else "(詳細不明: merge stderr を確認)"
            notify(f"{head_ref} <- {args.base} でコンフリクトを検出: {files}", is_error=True)
            if merge_result.stderr.strip():
                print(merge_result.stderr.strip())
            raise SystemExit(1)

        notify(f"{head_ref} <- {args.base} はコンフリクトなし", is_error=False)
    finally:
        git("worktree", "remove", "--force", str(tmpdir), cwd=repo_root, check=False)
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    main()