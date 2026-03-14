#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def current_branch(repo_root: Path) -> str:
    """現在のブランチ名を返す。"""
    result = git("rev-parse", "--abbrev-ref", "HEAD", cwd=repo_root)
    return result.stdout.strip()


def remote_exists(repo_root: Path, name: str) -> bool:
    """指定した remote が存在するか判定する。"""
    result = git("remote", cwd=repo_root)
    return name in result.stdout.splitlines()


def working_tree_clean(repo_root: Path) -> bool:
    """作業ツリーがクリーンか判定する。"""
    result = git("status", "--porcelain", cwd=repo_root)
    return result.stdout.strip() == ""


def switch_branch(repo_root: Path, branch: str) -> None:
    """指定ブランチへ切り替える。"""
    git("switch", branch, cwd=repo_root)


def main() -> None:
    """upstream から fork ブランチへ同期して push する。"""
    parser = argparse.ArgumentParser(description="upstream から fork ブランチへ同期して push する")
    parser.add_argument("--branch", default="main", help="同期対象ブランチ（既定: main）")
    parser.add_argument("--upstream-remote", default="upstream", help="upstream 側 remote 名")
    parser.add_argument("--fork-remote", default="origin", help="fork 側 remote 名")
    parser.add_argument("--allow-dirty", action="store_true", help="作業ツリーが汚れていても実行する")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    if not remote_exists(repo_root, args.upstream_remote):
        raise SystemExit(
            f"Remote '{args.upstream_remote}' が見つかりません。"
            f"先に `git remote add {args.upstream_remote} <UPSTREAM_URL>` を実行してください。"
        )

    if not remote_exists(repo_root, args.fork_remote):
        raise SystemExit(f"Remote '{args.fork_remote}' が見つかりません。")

    if not args.allow_dirty and not working_tree_clean(repo_root):
        raise SystemExit("作業ツリーに未コミット変更があります。コミットまたは退避してから再実行してください。")

    original_branch = current_branch(repo_root)
    target_ref = f"{args.upstream_remote}/{args.branch}"

    print(f"取得中: {target_ref}")
    git("fetch", args.upstream_remote, args.branch, cwd=repo_root)

    print(f"ブランチ切替: {args.branch}")
    switch_branch(repo_root, args.branch)

    print(f"fast-forward マージ: {target_ref}")
    try:
        git("merge", "--ff-only", target_ref, cwd=repo_root)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            "--ff-only でマージできませんでした。"
            "ローカルの main が分岐している可能性があります。\n"
            f"標準エラー: {error.stderr.strip()}"
        )

    print(f"push 実行: {args.fork_remote}/{args.branch}")
    git("push", args.fork_remote, args.branch, cwd=repo_root)

    if original_branch != args.branch:
        print(f"元のブランチへ復帰: {original_branch}")
        switch_branch(repo_root, original_branch)

    print("fork 同期が完了した。")


if __name__ == "__main__":
    main()