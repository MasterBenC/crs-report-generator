#!/usr/bin/env bash
# 一键安装 crs-report-generator skill 到指定 agents' skills 目录
# 用法: bash install.sh [目标目录]   (默认 ~/.claude/skills)
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/crs-report-generator"
TARGET="${1:-$HOME/.claude/skills}"

if [ ! -d "$SRC_DIR" ]; then
    echo "❌ 未找到 skill 源目录: $SRC_DIR" >&2
    exit 1
fi

# 若用户传了绝对路径到某个 skill 的上级，兼容
if [[ "$TARGET" == *"/crs-report-generator" ]]; then
    TARGET="$(dirname "$TARGET")"
fi

mkdir -p "$TARGET"
DEST="$TARGET/crs-report-generator"

# 安全复制（rsync 优先；无则用 cp -r，先清理已有的 __pycache__）
if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude='__pycache__' --exclude='*.pyc' "$SRC_DIR/" "$DEST/"
else
    rm -rf "$DEST"
    cp -r "$SRC_DIR" "$DEST"
    find "$DEST" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find "$DEST" -name '*.pyc' -delete 2>/dev/null || true
fi

echo "✅ 已安装到: $DEST"
echo "   依赖: pip install -r \"$DEST/requirements.txt\""
echo "   之后在对话里说「帮我算一下海外账户今年大概要补多少税」即可使用。"
