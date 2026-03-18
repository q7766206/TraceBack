# TraceBack 溯·源

## 跨平台安装指南

### 方法一：使用Python直接运行（推荐，跨平台）

#### 步骤1：安装Python 3.11+
- **Windows**：从 [Python官网](https://www.python.org/downloads/windows/) 下载并安装
- **macOS**：从 [Python官网](https://www.python.org/downloads/macos/) 下载并安装

#### 步骤2：安装依赖

```bash
# Windows
cd "C:\Users\Administrator\Desktop\TraceBack - 副本\backend"
pip install -r requirements.txt

# macOS
cd "~/Desktop/TraceBack - 副本/backend"
pip3 install -r requirements.txt
```

#### 步骤3：启动应用

```bash
# Windows
python run.py

# macOS
python3 run.py
```

#### 步骤4：访问应用
打开浏览器访问：`http://localhost:5001`

### 方法二：使用打包版本（平台特定）

#### Windows
- 运行 `backend/dist/TraceBack.exe`

#### macOS
需要在macOS环境下重新打包：

```bash
cd "~/Desktop/TraceBack - 副本/backend"
pip3 install pyinstaller
pyinstaller --onefile --name TraceBack --add-data "../frontend/dist:frontend/dist" run.py

# 运行
./dist/TraceBack
```

## 功能特性

### 1. 实时图谱渲染
- 在第二步图谱构建过程中，左侧空白区域会实时显示图谱变化
- 支持Zep Cloud和本地模式的实时更新

### 2. 安全的API密钥管理
- 配置文件存储在用户目录下（`.traceback_env`）
- 避免API密钥被包含在打包文件中

### 3. 强化的Agent人设
- 实现了五维强化方案
- 包含7个专业Agent
- 支持三模式输出（专家/执行/公众）

## 技术栈

- **后端**：Flask 3.0+
- **前端**：Vue 3 + D3.js
- **图谱**：Zep Cloud（优先）/ 本地LSTM
- **LLM**：OpenAI API

## 系统要求

- Python 3.11+
- 至少 4GB RAM
- 稳定的网络连接（使用Zep Cloud时）

## 常见问题

### Q: 启动时提示缺少API密钥
A: 应用可以在没有API密钥的情况下运行，只是某些功能会受限。

### Q: 图谱构建速度很慢
A: 这是正常现象，特别是在使用本地模式时。使用Zep Cloud会显著提高速度。

### Q: 应用在macOS上运行时出现权限问题
A: 请在系统设置 > 安全性与隐私 > 通用中允许来自"不明开发者"的应用。

## 联系方式

如有问题，请联系项目维护者。