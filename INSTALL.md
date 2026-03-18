# TraceBack 跨平台安装指南

## 系统要求

- Python 3.11 或更高版本
- 至少 4GB RAM
- 稳定的网络连接（使用Zep Cloud时）

## Windows 系统

### 方法一：使用打包版本（推荐）

1. **下载并解压**
   - 从提供的压缩包中解压 `TraceBack - 副本` 文件夹到桌面

2. **运行应用**
   - 打开 `backend\dist` 文件夹
   - 双击 `TraceBack.exe` 运行应用

3. **访问应用**
   - 打开浏览器访问：`http://localhost:5001`

### 方法二：使用Python直接运行

1. **安装Python**
   - 从 [Python官网](https://www.python.org/downloads/windows/) 下载并安装 Python 3.11+
   - 确保勾选 "Add Python to PATH"

2. **安装依赖**
   - 打开命令提示符（cmd）
   - 运行：
     ```bash
     cd "C:\Users\Administrator\Desktop\TraceBack - 副本\backend"
     pip install -r requirements.txt
     ```

3. **启动应用**
   ```bash
   python run.py
   ```

4. **访问应用**
   - 打开浏览器访问：`http://localhost:5001`

## macOS 系统

### 方法一：使用Python直接运行（推荐）

1. **安装Python**
   - 从 [Python官网](https://www.python.org/downloads/macos/) 下载并安装 Python 3.11+
   - 或者使用 Homebrew：`brew install python3`

2. **安装依赖**
   - 打开终端（Terminal）
   - 运行：
     ```bash
     cd "~/Desktop/TraceBack - 副本/backend"
     pip3 install -r requirements.txt
     ```

3. **启动应用**
   ```bash
   python3 run.py
   ```

4. **访问应用**
   - 打开浏览器访问：`http://localhost:5001`

### 方法二：在macOS上打包

1. **安装PyInstaller**
   ```bash
   pip3 install pyinstaller
   ```

2. **打包应用**
   ```bash
   cd "~/Desktop/TraceBack - 副本/backend"
   pyinstaller --onefile --name TraceBack --add-data "../frontend/dist:frontend/dist" run.py
   ```

3. **运行应用**
   ```bash
   ./dist/TraceBack
   ```

4. **访问应用**
   - 打开浏览器访问：`http://localhost:5001`

## 首次运行

1. **启动应用**后，您会看到命令行窗口显示服务启动信息
2. **打开浏览器**访问 `http://localhost:5001`
3. **开始使用**：
   - 上传文档
   - 输入模拟需求
   - 点击 "开始分析"
   - 在第二步图谱构建过程中，左侧会实时显示图谱变化

## 常见问题

### Q: 启动时提示缺少API密钥
A: 应用可以在没有API密钥的情况下运行，只是某些功能会受限。

### Q: 图谱构建速度很慢
A: 这是正常现象，特别是在使用本地模式时。使用Zep Cloud会显著提高速度。

### Q: 应用在macOS上运行时出现权限问题
A: 请在系统设置 > 安全性与隐私 > 通用中允许来自"不明开发者"的应用。

### Q: 浏览器无法访问应用
A: 请检查：
- 后端服务是否正在运行
- 地址是否正确（`http://localhost:5001`）
- 端口5001是否被占用

## 技术支持

如有问题，请联系项目维护者。