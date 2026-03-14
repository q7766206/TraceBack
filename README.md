<div align="center">

# TraceBack 溯·源

**基于多智能体技术的因果回溯分析引擎**

*A Multi-Agent Causal Retrospection Engine*

[![GitHub Stars](https://img.shields.io/github/stars/traceback-ai/TraceBack?style=flat-square&color=DAA520)]()
[![License](https://img.shields.io/badge/License-GPL--2.0-blue?style=flat-square)]()

</div>

## ⚡ 项目概述

**TraceBack（溯·源）** 是一款基于多智能体技术的因果回溯分析引擎。输入一个事件或问题，TraceBack 会自动调度 7 个专业 AI Agent 协作完成数据采集、时间线重建、因果推理、证据审计、质证辩论，最终输出带有完整证据链和置信度评估的回溯分析报告。

> BettaFish/MiroFish 预测未来，TraceBack 回溯过去 —— 同一套多 Agent 架构的两面。

## 🎯 核心能力

- **7 个专业 Agent 协作**：档案猎手、时序分析师、因果侦探、证据审计官、魔鬼代言人、取证主持人、回溯报告官
- **因果网络图**：自动构建有向因果关系网络，区分直接/间接/根本原因
- **质证辩论机制**：Agent 之间进行多轮质证辩论，魔鬼代言人专门负责质疑和寻找反例
- **证据链闭环**：每个结论都可追溯到原始证据，五层幻觉抑制
- **置信度评估**：所有结论标注置信度，诚实声明不确定性

## 🔄 工作流程

1. **图谱构建**：上传相关资料 → LLM 自动设计因果本体 → Zep 构建知识图谱
2. **分析配置**：设置回溯任务、时间范围、分析深度
3. **质证分析**：7 个 Agent 按阶段协作 → 数据采集 → 时间线重建 → 因果推理 → 证据审计 → 质证辩论 → 共识形成
4. **报告生成**：ReACT 模式生成结构化报告，含时间线图、因果网络图、证据链
5. **深度互动**：与任意 Agent 对话，深入探讨分析结果

## 🚀 快速开始

### 前置要求

| 工具 | 版本要求 | 说明 |
|------|---------|------|
| **Node.js** | 18+ | 前端运行环境 |
| **Python** | ≥3.11, ≤3.12 | 后端运行环境 |
| **uv** | 最新版 | Python 包管理器 |

### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入 LLM_API_KEY 和 ZEP_API_KEY
```

### 2. 安装依赖

```bash
# 前端
cd frontend && npm install

# 后端
cd backend && uv sync
```

### 3. 启动服务

```bash
# 后端
cd backend && uv run python run.py

# 前端（新终端）
cd frontend && npm run dev
```

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`

## 🏗️ 技术架构

- **后端**：Python + Flask + Zep Cloud (GraphRAG) + OpenAI SDK
- **前端**：Vue 3 + Vite + D3.js
- **知识图谱**：Zep Cloud（免费额度即可使用）
- **LLM**：支持任意 OpenAI 格式 API（推荐 qwen-plus / GPT-4o / DeepSeek-R1）

## 📬 致谢

本项目架构灵感来源于 [MiroFish](https://github.com/666ghj/MiroFish) 和 [BettaFish](https://github.com/666ghj/BettaFish)，感谢 666ghj 的开源贡献。
