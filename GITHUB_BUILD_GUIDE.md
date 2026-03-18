# TraceBack Desktop - GitHub Actions 自动打包指南

## 概述

本项目已配置 GitHub Actions 工作流，可以自动在云端打包 Windows 和 macOS 双平台应用。

## 文件说明

- `.github/workflows/build.yml` - GitHub Actions 工作流配置
- `backend/TraceBackDesktop.spec` - Windows 打包配置
- `backend/TraceBackDesktop_macos.spec` - macOS 打包配置

## 如何触发打包

### 方式 1：推送代码时自动触发

```bash
git add .
git commit -m "更新版本"
git push origin main
```

### 方式 2：手动触发

1. 打开 GitHub 仓库页面
2. 点击 **Actions** 标签
3. 选择 **Build Cross-Platform Desktop App**
4. 点击 **Run workflow** → **Run workflow**

### 方式 3：打标签发布

```bash
git tag -a v0.1.0 -m "版本 0.1.0"
git push origin v0.1.0
```

打标签后会自动创建 Release 并上传打包好的文件。

## 打包输出

打包完成后，可以在以下位置下载：

1. **GitHub Actions 页面** - 每次运行后生成的 Artifacts
2. **Release 页面** - 打标签后自动发布

### 输出文件

- `TraceBackDesktop-Windows.zip` - Windows 版本
- `TraceBackDesktop-macOS.zip` - macOS 版本 (.app)

## 首次使用前的准备

### 1. 确保代码已推送到 GitHub

```bash
git init
git add .
git commit -m "初始提交"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

### 2. 检查 requirements.txt

确保 `backend/requirements.txt` 包含所有依赖：

```
flask
pyqt5
pyqtwebengine
requests
werkzeug
# ... 其他依赖
```

### 3. 测试本地打包（可选）

Windows 本地测试：
```bash
cd backend
pyinstaller TraceBackDesktop.spec
```

## 注意事项

1. **macOS 打包时间** - macOS 打包通常需要 10-20 分钟
2. **文件大小** - 每个平台打包后约 200-500MB
3. **代码签名** - 当前配置未启用代码签名，macOS 用户可能需要在"系统偏好设置 → 安全性与隐私"中允许运行
4. **Python 版本** - 使用 Python 3.11

## 常见问题

### Q: macOS 用户无法打开应用？
A: 由于未代码签名，macOS 会提示"无法验证开发者"。用户需要：
1. 右键点击应用 → 打开
2. 或在 系统偏好设置 → 安全性与隐私 → 通用 中点击"仍要打开"

### Q: 如何启用代码签名？
A: 需要 Apple Developer 账号，并在 GitHub Secrets 中配置签名证书。

### Q: 打包失败怎么办？
A: 查看 GitHub Actions 日志，常见问题：
- 依赖缺失 → 更新 requirements.txt
- 前端构建失败 → 检查 frontend/package.json

## 技术支持

如有问题，请查看 GitHub Actions 运行日志或联系技术支持。
