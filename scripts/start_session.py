#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


def next_session_number(sessions_root: Path) -> str:
    """sessions 配下から次のセッション番号を算出する。"""
    sessions_root.mkdir(parents=True, exist_ok=True)

    max_value = 0
    for child in sessions_root.iterdir():
        if child.is_dir() and re.fullmatch(r"\d+", child.name):
            max_value = max(max_value, int(child.name))

    return f"{max_value + 1:03d}"


def run_python_script(repo_root: Path, script: str, *args: str) -> None:
    """scripts 配下の Python スクリプトを実行する。"""
    subprocess.run(
        ["python", f"scripts/{script}", *args],
        cwd=repo_root,
        check=True,
    )


def main() -> None:
    """同一セッション番号でブランチ作成とファイル作成を順に実行する。"""
    parser = argparse.ArgumentParser(description="同一セッション番号で安全にセッション開始処理を実行する")
    parser.add_argument("--session", default="", help="セッション番号（例: 001）。未指定時は自動採番")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    sessions_root = repo_root / "sessions"
    sessions_root.mkdir(parents=True, exist_ok=True)

    session = args.session if args.session else next_session_number(sessions_root)
    print(f"対象セッション番号: {session}")

    print("手順 1/2: ブランチを作成して push")
    run_python_script(repo_root, "create_session_branch.py", "--session", session)

    print("手順 2/2: セッションファイルを作成")
    run_python_script(repo_root, "create_session_files.py", "--session", session)

    print(f"セッション開始処理が完了: {session}")


if __name__ == "__main__":
    main()
