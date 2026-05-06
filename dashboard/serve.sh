#!/bin/bash
# Dalio 看板一键启动 — 自动刷新数据 + HTTP 服务
# 用法: bash serve.sh [port]

PORT=${1:-8502}
DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="$(cd "$DIR/.." && pwd)"

echo "🔮 Dalio 宏观协同总指挥 V7"
echo "   项目: $PROJECT"
echo ""

# 1. 刷新数据（如果 data.json 不存在或超过 6 小时）
NEED_REFRESH=0
if [ ! -f "$DIR/data.json" ]; then
    echo "📦 data.json 不存在，正在生成..."
    NEED_REFRESH=1
elif [ "$(find "$DIR/data.json" -mmin +360 2>/dev/null)" ]; then
    echo "📦 data.json 超过6小时，刷新..."
    NEED_REFRESH=1
fi

if [ "$NEED_REFRESH" = "1" ]; then
    cd "$PROJECT"
    python dashboard/export_data.py 2>&1 | tail -2
    echo ""
fi

# 2. 检查 DB 是否存在
if [ ! -f "$PROJECT/macro.db" ]; then
    echo "⚠️  macro.db 不存在，请先运行: bash run_daily.sh"
    echo "   然后重新执行: bash dashboard/serve.sh"
    exit 1
fi

# 3. 启动 HTTP 服务
echo "🌐 看板启动: http://localhost:$PORT"
echo "   按 Ctrl+C 停止"
echo ""
cd "$DIR"
python3 -m http.server "$PORT"
