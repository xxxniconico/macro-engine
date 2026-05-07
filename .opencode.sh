#!/bin/bash
# ~/macro-engine/.opencode.sh
# OpenCode + Hermes 协作快捷命令
# source 此文件即可使用

export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-your-key-here}"
OC="opencode run"

# ═══════════════════════════════════════════
# 快捷命令
# ═══════════════════════════════════════════

# 1. 写新文件 — "给我写一个 xxx.py"
oc-new() {
    echo "📝 OpenCode 写新文件: $*"
    $OC "$*" --model deepseek/deepseek-v4-pro
}

# 2. 重构 — 跨文件改，自动跑测试
oc-refactor() {
    echo "🔧 OpenCode 重构: $*"
    $OC "$* --test-first" --model deepseek/deepseek-v4-pro
}

# 3. 数据处理 — 一次性子脚本
oc-data() {
    echo "📊 OpenCode 数据处理: $*"
    $OC "$*" --model deepseek/deepseek-v4-flash  # Flash 够快够便宜
}

# 4. 在 macro-engine 项目中工作
oc-macro() {
    cd ~/macro-engine
    echo "🔮 OpenCode (macro-engine): $*"
    $OC "$*" --model deepseek/deepseek-v4-pro
}

# 5. 批量文件操作
oc-batch() {
    echo "📦 OpenCode 批量: $*"
    $OC "$*" --model deepseek/deepseek-v4-pro
}

echo "🐾 OpenCode aliases loaded: oc-new oc-refactor oc-data oc-macro oc-batch"
