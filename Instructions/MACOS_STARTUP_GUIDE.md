# 🍎 macOS 启动指南

## 概述

为 macOS 用户提供了两个启动脚本：
- `start_project.sh` - 完整版本，包含环境检查和详细设置
- `start_macos.sh` - 简化版本，快速启动

## 🚀 快速开始

### 方法1：使用简化脚本（推荐）

```bash
# 在项目根目录运行
./start_macos.sh
```

### 方法2：使用完整脚本

```bash
# 在项目根目录运行
./start_project.sh
```

## 📋 前置要求

### 必需软件
- **Python 3.8+** - 后端运行环境
- **Node.js 16+** - 前端运行环境
- **npm** - 包管理器

### 安装方法

#### 使用 Homebrew（推荐）
```bash
# 安装 Homebrew（如果未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python
brew install python

# 安装 Node.js
brew install node
```

#### 使用官方安装包
- **Python**: 从 [python.org](https://www.python.org/downloads/) 下载
- **Node.js**: 从 [nodejs.org](https://nodejs.org/) 下载

## 🔧 脚本功能

### start_macos.sh（简化版）
- ✅ 环境检查（Python、Node.js、npm）
- ✅ 创建虚拟环境
- ✅ 安装依赖
- ✅ 启动后端服务（新终端窗口）
- ✅ 启动前端服务（新终端窗口）

### start_project.sh（完整版）
- ✅ 详细的环境检查
- ✅ 完整的依赖安装
- ✅ 错误处理和验证
- ✅ 彩色输出和进度提示
- ✅ 自动清理临时文件

## 🖥️ 使用说明

### 1. 打开终端
按 `Cmd + Space` 搜索 "Terminal" 或从应用程序文件夹打开

### 2. 导航到项目目录
```bash
cd /path/to/article_recommendation_project
```

### 3. 运行启动脚本
```bash
# 简化版本
./start_macos.sh

# 或完整版本
./start_project.sh
```

### 4. 等待服务启动
- 后端服务会在新终端窗口中启动
- 前端服务会在另一个新终端窗口中启动
- 等待编译完成（约1-2分钟）

## 🌐 访问应用

启动完成后，访问以下地址：

- **前端应用**: http://localhost:5173
- **后端API**: http://127.0.0.1:8000
- **API文档**: http://127.0.0.1:8000/docs

## 👤 测试账户

- **用户名**: student_zhang
- **密码**: password

## 🛠️ 故障排除

### 权限问题
如果遇到权限错误，运行：
```bash
chmod +x start_macos.sh
chmod +x start_project.sh
```

### Python 版本问题
确保使用 Python 3.8+：
```bash
python3 --version
```

### Node.js 版本问题
确保使用 Node.js 16+：
```bash
node --version
```

### 端口占用
如果端口被占用，可以修改：
- 后端端口：编辑 `backend/start_dev.py`
- 前端端口：编辑 `frontend/vite.config.ts`

### 虚拟环境问题
如果虚拟环境有问题，删除并重新创建：
```bash
rm -rf article_recommend
python3 -m venv article_recommend
```

## 🔄 停止服务

要停止服务，关闭相应的终端窗口或按 `Ctrl + C`

## 📝 注意事项

1. **首次运行**：需要下载依赖，可能需要5-10分钟
2. **网络要求**：需要网络连接下载依赖包
3. **存储空间**：确保有足够的磁盘空间（约2GB）
4. **防火墙**：确保防火墙允许本地端口访问

## 🆘 获取帮助

如果遇到问题：
1. 检查终端输出中的错误信息
2. 确保所有前置要求已满足
3. 尝试重新运行脚本
4. 检查网络连接

## 🎯 下一步

启动成功后：
1. 访问 http://localhost:5173
2. 使用测试账户登录
3. 探索学术论文推荐功能
4. 查看 API 文档了解后端接口

享受使用学术论文推荐系统！🎉
