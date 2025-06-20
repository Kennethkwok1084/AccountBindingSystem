#!/bin/bash
# ⚙️ Codex 任务初始化脚本
# 用于安装依赖、配置环境、准备测试环境

echo "🚀 正在初始化项目环境..."

# ---------- Python 环境 ----------
echo "🐍 安装后端 Python 依赖..."
cd backend

# 使用 virtualenv（可选）
# python -m venv venv
# source venv/bin/activate

# 安装 Python 依赖（requirements.txt 需提前准备好）
pip install -r requirements.txt

# 若未指定数据库类型，则默认使用 SQLite
export USE_SQLITE=${USE_SQLITE:-1}

# 安装 Alembic（用于数据库迁移）
pip install alembic

cd ..

# ---------- Node/Vue 环境 ----------
echo "🌐 安装前端 Vue 依赖..."
cd frontend

# 使用 npm 安装（也可以改成 pnpm/yarn）
npm install

# 安装 vitest 用于测试（如已集成）
npm install --save-dev vitest

cd ..

# ---------- 环境变量 ----------
echo "🔧 设置默认环境变量..."
export FLASK_ENV=development
export DATABASE_URL="sqlite:///backend/local.db"
export VITE_API_BASE="http://localhost:5000/api"

# ---------- 提示完成 ----------
echo "✅ 项目初始化完成！"
echo "🎉 Codex 现在可以开始写代码啦！"
