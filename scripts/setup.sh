#!/usr/bin/env bash
# 機能:
#  - mise が未インストールなら homebrew を優先してインストールし、なければ curl インストーラを実行する
#  - シェル種別（bash / zsh / fish）に応じて rc ファイルに mise の activate 行を追記（バックアップ作成）
#  - 追記後に同種のサブシェルを起動して activate スクリプトを即時評価（即時反映を試みる）
#  - `mise install` を試行し、存在しなければ `mise doctor` をフォールバックで実行
#
# 使い方:
#   対話モード (確認あり):
#     bash scripts/setup.sh
#   非対話モード (すべて yes):
#     bash scripts/setup.sh --yes
#

# NOTE: このスクリプトは bash が必要です。誤って sh で実行された場合は
#       下のガードで自動的に bash に切り替えて再実行します。

# ----- bash 実行ガード -----
# sh などで実行された場合は bash で再実行する
if [ -z "${BASH_VERSION:-}" ]; then
  # POSIX sh で実行されている → bash を探して再実行
  if command -v bash >/dev/null 2>&1; then
    exec bash "$0" "$@"
  else
    echo "このスクリプトは Bash が必要です。bash が見つかりません。" >&2
    exit 1
  fi
fi

set -euo pipefail

# --- 設定 ---
SKIP_PROMPTS=false
if [ "${1:-}" = "--yes" ] || [ "${1:-}" = "-y" ]; then
  SKIP_PROMPTS=true
fi

timestamp() { date -u +"%Y%m%dT%H%M%SZ"; }

# --- ヘルパー ---
err() { printf '%s\n' "$*" >&2; }

# 確認プロンプト（非対話モードなら自動 yes）
confirm_or_exit() {
  local msg="${1:-Proceed?}"
  if [ "$SKIP_PROMPTS" = true ]; then
    printf '%s (自動了承)\n' "$msg"
    return 0
  fi
  printf "%s [y/N] " "$msg"
  read -r ans || true
  case "${ans,,}" in
    y|yes) return 0 ;;
    *) err "ユーザーにより中止されました。"; exit 1 ;;
  esac
}

# シェル判定（$SHELL と親プロセスのコマンド名を利用）
detect_shell() {
  local s=""
  if [ -n "${SHELL:-}" ]; then
    s="$(basename "$SHELL")"
    s="${s,,}"
  fi

  if command -v ps >/dev/null 2>&1; then
    local ppid parent_cmd
    ppid="$(ps -p $$ -o ppid= 2>/dev/null || true)"
    if [ -n "$ppid" ]; then
      parent_cmd="$(ps -p "$ppid" -o comm= 2>/dev/null || true)"
      parent_cmd="$(basename "$parent_cmd" 2>/dev/null || true)"
      parent_cmd="${parent_cmd,,}"
      case "$parent_cmd" in
        bash|zsh|fish|sh|ksh|tcsh|csh) s="$parent_cmd" ;;
      esac
    fi
  fi

  case "$s" in
    zsh) echo "zsh" ;;
    fish) echo "fish" ;;
    bash) echo "bash" ;;
    sh) echo "bash" ;;    # sh を bash 互換扱いにする
    *) echo "bash" ;;     # デフォルトは bash
  esac
}

# rc ファイルに 'mise activate' を含む行がなければ追記し、バックアップを作る
append_activation() {
  local rcfile="$1"; shift
  local line="$*"
  mkdir -p "$(dirname "$rcfile")"
  touch "$rcfile"

  # 既に 'mise activate' を参照する行があれば追記をスキップ
  if grep -F -q "mise activate" "$rcfile"; then
    printf '既に %s に activation 行が存在します。追加はスキップします。\n' "$rcfile"
    return 0
  fi

  # バックアップ
  local bak="${rcfile}.mise.bak.$(timestamp)"
  if cp -a "$rcfile" "$bak" 2>/dev/null; then
    printf 'バックアップ作成: %s\n' "$bak"
  else
    printf '警告: %s のバックアップを作成できませんでした（パーミッション等）。続行します。\n' "$rcfile"
  fi

  # マーカー付きで追記
  {
    printf '\n# Added by setup.sh on %s\n' "$(timestamp)"
    printf '%s\n' "$line"
  } >> "$rcfile"
  printf '追記しました: %s に activation 行を追加しました。\n' "$rcfile"
}

# mise activate の出力を一時ファイルに書き、それを同種のサブシェルで source して即時反映を試みる
eval_activation_now() {
  local shellname="$1"
  local mise_cmd="$2" # フルパスでもコマンド名でも可
  local tmpf
  tmpf="$(mktemp "/tmp/mise_activate.${shellname}.XXXXXX")"
  # activate スクリプトを生成
  if ! "$mise_cmd" activate "$shellname" > "$tmpf" 2>/dev/null; then
    err "シェル用 activate スクリプトを生成できませんでした: $shellname ($mise_cmd)"
    rm -f "$tmpf"
    return 1
  fi

  # シェルごとにサブシェルで source して評価（各シェルの文法で解釈される）
  case "$shellname" in
    bash|sh)
      bash -lc "source '$tmpf' && printf 'mise を bash サブシェルで有効化しました\n'"
      ;;
    zsh)
      zsh -lc "source '$tmpf' && printf 'mise を zsh サブシェルで有効化しました\n'"
      ;;
    fish)
      # fish は `source` を用いるが、fish プロセスで実行する必要がある
      fish -c "source '$tmpf'; printf 'mise を fish サブシェルで有効化しました\n'"
      ;;
    *)
      bash -lc "source '$tmpf' && printf 'mise をサブシェルで有効化しました (fallback: bash)\n'"
      ;;
  esac

  rm -f "$tmpf"
  return 0
}

# ~/.local/bin を PATH に追加（このプロセス内のみ）
export PATH="$HOME/.local/bin:$PATH"

# mise のインストールを試みる（already_installed / MISE_BIN グローバル変数を参照・更新する）
install_mise() {
  if [ "$already_installed" = false ]; then
    if command -v brew >/dev/null 2>&1; then
      printf "Homebrew が検出されました。まず brew install mise を試行します。\n"
      confirm_or_exit "brew install mise を実行してよいですか?"
      if brew install mise; then
        printf "brew install mise が成功しました。\n"
        MISE_BIN="$(command -v mise || echo "$MISE_BIN")"
      else
        err "brew でのインストールに失敗しました。curl インストーラにフォールバックします。"
        confirm_or_exit "curl インストーラ (curl https://mise.run | sh) を実行してよいですか?"
        if ! command -v curl >/dev/null 2>&1; then
          err "curl が見つかりません。インストールできません。終了します。"
          exit 1
        fi
        curl -fsSL https://mise.run | sh
        MISE_BIN="$HOME/.local/bin/mise"
      fi
    else
      printf "Homebrew が見つかりません。curl インストーラを実行します。\n"
      confirm_or_exit "curl インストーラ (curl https://mise.run | sh) を実行してよいですか?"
      if ! command -v curl >/dev/null 2>&1; then
        err "curl が見つかりません。インストールできません。終了します。"
        exit 1
      fi
      curl -fsSL https://mise.run | sh
      MISE_BIN="$HOME/.local/bin/mise"
    fi
  else
    printf "インストールはスキップします: mise が既に存在します。\n"
  fi

  # MISE_BIN の確認
  if [ -x "$MISE_BIN" ]; then
    printf "使用する mise バイナリ: %s\n" "$MISE_BIN"
  else
    if command -v mise >/dev/null 2>&1; then
      MISE_BIN="$(command -v mise)"
      printf "PATH 上に mise を検出しました: %s\n" "$MISE_BIN"
    else
      err "mise をインストールしましたがバイナリが見つかりません。PATH を確認してください。終了します。"
      exit 1
    fi
  fi
}

# rc ファイルへの activation 行追記と即時有効化を行う（RCFILE グローバル変数を設定する）
setup_activation() {
  local ACTIVATION_LINE
  case "$USER_SHELL" in
    bash)
      RCFILE="$HOME/.bashrc"
      # ~/.local/bin に置かれている場合は明示パスで記述
      if [ "${MISE_BIN#"$HOME/.local/bin/"}" != "$MISE_BIN" ]; then
        ACTIVATION_LINE='eval "$(~/.local/bin/mise activate bash)"'
      else
        ACTIVATION_LINE='eval "$(mise activate bash)"'
      fi
      ;;
    zsh)
      RCFILE="$HOME/.zshrc"
      if [ "${MISE_BIN#"$HOME/.local/bin/"}" != "$MISE_BIN" ]; then
        ACTIVATION_LINE='eval "$(~/.local/bin/mise activate zsh)"'
      else
        ACTIVATION_LINE='eval "$(mise activate zsh)"'
      fi
      ;;
    fish)
      RCFILE="$HOME/.config/fish/config.fish"
      if [ "${MISE_BIN#"$HOME/.local/bin/"}" != "$MISE_BIN" ]; then
        # fish 用には eval (cmd) 構文を使う
        ACTIVATION_LINE='eval (~/.local/bin/mise activate fish)'
      else
        ACTIVATION_LINE='eval (mise activate fish)'
      fi
      ;;
    *)
      RCFILE="$HOME/.bashrc"
      ACTIVATION_LINE='eval "$(mise activate bash)"'
      ;;
  esac

  # rc ファイルに追記（重複チェック + バックアップ）
  append_activation "$RCFILE" "$ACTIVATION_LINE"

  # 追記後、同種のサブシェルで即時有効化を試みる（安全にサブシェルで評価）
  printf '即時有効化を試みます（サブシェルで評価）: %s\n' "$USER_SHELL"
  if ! eval_activation_now "$USER_SHELL" "$MISE_BIN"; then
    err "即時有効化に失敗しました。新しいシェルを開くか、次を実行してください: source $RCFILE"
  else
    printf '即時有効化を試行しました。シェルに反映されない場合は: source %s かシェルの再起動を行ってください。\n' "$RCFILE"
  fi
}

# --- メイン処理 ---
main() {
  printf '=== mise セットアップ開始 ===\n'

  USER_SHELL="$(detect_shell)"
  printf '検出されたシェル: %s\n' "$USER_SHELL"

  # mise の存在チェック
  if command -v mise >/dev/null 2>&1; then
    MISE_BIN="$(command -v mise)"
    printf '既に mise が見つかりました: %s\n' "$MISE_BIN"
    already_installed=true
  else
    already_installed=false
    MISE_BIN="$HOME/.local/bin/mise"
  fi

  install_mise

  setup_activation

  # mise install の試行、なければ mise doctor を実行
  printf "mise の追加セットアップを試行します（'mise install' を優先）。\n"
  export PATH="$HOME/.local/bin:$PATH"

  # install サブコマンドの存在を簡易チェック
  if "$MISE_BIN" --help 2>&1 | grep -qi 'install'; then
    # --yes 等の非対話フラグの有無をチェック（あれば利用を試みる）
    if "$MISE_BIN" install --help 2>&1 | grep -Ei -- '--yes|--assume-yes|--non-interactive' >/dev/null 2>&1; then
      if "$MISE_BIN" install --yes 2>/dev/null; then
        printf "'mise install --yes' が成功しました。\n"
      else
        err "'mise install --yes' に失敗しました。対話式で 'mise install' を実行します。"
        if "$MISE_BIN" install; then
          printf "'mise install' が成功しました。\n"
        else
          err "'mise install' が失敗しました。代わりに 'mise doctor' を実行します。"
          "$MISE_BIN" doctor || err "'mise doctor' も失敗しました。手動で確認してください。"
        fi
      fi
    else
      # --yes をサポートしない場合はそのまま実行（対話の可能性あり）
      if "$MISE_BIN" install 2>/dev/null; then
        printf "'mise install' が成功しました。\n"
      else
        err "'mise install' に失敗しました。'mise doctor' を実行します。"
        "$MISE_BIN" doctor || err "'mise doctor' も失敗しました。手動で確認してください。"
      fi
    fi
  else
    # install サブコマンドがない可能性が高い -> doctor を実行
    if "$MISE_BIN" doctor 2>/dev/null; then
      printf "'mise doctor' が成功しました。\n"
    else
      err "'mise doctor' に失敗しました。手動で 'mise doctor' を実行してください。\n"
    fi
  fi

  printf '=== 完了 ===\n'
  printf '注意: 追記した %s を有効にするには、シェルを再起動するか次を実行してください:\n  source %s\n' "$RCFILE" "$RCFILE"
}

main "$@"