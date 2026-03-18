# TraceBack 溯·源

## 快速下载（推荐）

### 预编译版本

每次代码更新后，GitHub Actions 会自动构建 Windows 和 macOS 版本的桌面应用：

| 系统 | 下载方式 | 文件大小 |
|------|---------|---------|
| **Windows** | [GitHub Releases](https://github.com/q7766206/TraceBack/releases) 下载 `TraceBack-Windows.zip` | ~50MB |
| **macOS** | [GitHub Releases](https://github.com/q7766206/TraceBack/releases) 下载 `TraceBack-macOS.zip` | ~60MB |

### 安装步骤

#### Windows
1. 下载 `TraceBack-Windows.zip`
2. 解压到任意文件夹
3. 双击运行 `TraceBack.exe`
4. 浏览器会自动打开 `http://localhost:5001`

> ⚠️ **注意**：Windows 可能会提示"未知发布者"，点击"更多信息"→"仍要运行"即可

#### macOS
1. 下载 `TraceBack-macOS.zip`
2. 解压到应用程序文件夹
3. **右键点击** `TraceBack.app` → 选择"打开"
4. 浏览器会自动打开 `http://localhost:5001`

> ⚠️ **注意**：macOS 会提示"无法验证开发者"，需要在 系统设置 → 隐私与安全性 → 安全性 中点击"仍要打开"

---

## 开发者运行方式（Python）

如果你想修改代码或从源码运行，请参考以下步骤：

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

### Q: 下载后无法运行？
**Windows**：
- 如果提示"Windows 已保护你的电脑"，点击"更多信息"→"仍要运行"
- 确保已安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

**macOS**：
- 不要直接双击打开，需要**右键点击**→"打开"
- 如果仍无法打开，前往 系统设置 → 隐私与安全性 → 安全性，点击"仍要打开"

### Q: 启动时提示缺少API密钥
A: 应用可以在没有API密钥的情况下运行，只是某些功能会受限。首次运行时会提示配置。

### Q: 图谱构建速度很慢
A: 这是正常现象，特别是在使用本地模式时。使用Zep Cloud会显著提高速度。

### Q: 如何更新到最新版本？
A: 直接下载最新版本的 Release 文件，解压覆盖旧版本即可。配置文件会自动保留。

## 联系方式

如有问题，请联系项目维护者。