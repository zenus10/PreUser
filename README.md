# PreUser

**PRD 自动化压力测试平台** — 上传产品需求文档（PRD），AI 自动生成虚拟用户并模拟真实使用场景，发现产品盲区与体验瓶颈。

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![React](https://img.shields.io/badge/React-18-61dafb)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688)
![License](https://img.shields.io/badge/License-MIT-green)

## 核心能力

- **文档智能解析** — 支持 PDF / DOCX 格式 PRD 上传，自动提取结构化信息
- **知识图谱构建** — 基于 LLM 多轮 Chain 将 PRD 拆解为功能节点与依赖关系图谱
- **虚拟用户生成** — 自动生成多元化用户画像（Persona），可手动编辑调整
- **多场景叙事仿真** — 每个虚拟用户独立模拟操作路径，生成体验叙事
- **压测报告** — 汇总盲区（blind spots）与瓶颈（bottlenecks），输出可视化报告
- **深度交互对话** — 基于分析结果的 AI 问答，深入探索产品问题

## 技术架构

```
┌──────────────────────────────────────────────────┐
│                  Frontend (React)                │
│         React 18 + TypeScript + Tailwind         │
│     React Flow · Recharts · Framer Motion        │
├──────────────────────────────────────────────────┤
│                  Backend (FastAPI)                │
│        LiteLLM · SQLAlchemy · AsyncPG            │
│     5-Stage LLM Pipeline with Checkpoints        │
├───────────────────┬──────────────────────────────┤
│   PostgreSQL 16   │         Redis 7              │
└───────────────────┴──────────────────────────────┘
```

### 分析流水线（5-Stage Pipeline）

| 阶段 | 名称 | 说明 |
|------|------|------|
| Chain 1 | 结构感知 | 将 PRD 拆分为语义信息块（blocks） |
| Chain 2 / 2.5 | 关系抽取 & 图谱融合 | 提取功能依赖关系，构建知识图谱 |
| Chain 3 | 画像生成 | 基于图谱生成多元虚拟用户 |
| Chain 4 | 叙事仿真 | 每个用户模拟多场景操作路径 |
| Chain 5 | 报告生成 | 汇总发现盲区与瓶颈 |

每个阶段支持 **断点续跑（Checkpoint）**，失败后可从上次成功的阶段恢复。

## 快速开始

### 前置依赖

- Python 3.11+
- Node.js 18+
- PostgreSQL 16
- Redis 7
- DeepSeek API Key（或其他 LiteLLM 支持的 LLM API）

### 1. 克隆项目

```bash
git clone https://github.com/your-username/virtual-user-lab.git
cd virtual-user-lab
```

### 2. 启动数据库（Docker）

```bash
docker compose up -d
```

这会启动 PostgreSQL 和 Redis。如果你已有本地数据库，可以跳过此步。

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 API Key 和数据库密码：

```env
# 必填：你的 LLM API Key
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# 数据库密码
DB_PASSWORD=your_db_password_here
```

同时在 `backend/` 目录下也创建 `.env`：

```bash
cp .env.example backend/.env
```

> **获取 DeepSeek API Key：** 访问 [DeepSeek 开放平台](https://platform.deepseek.com/) 注册并创建 API Key。也支持其他 [LiteLLM 兼容的模型](https://docs.litellm.ai/docs/providers)，修改 `LLM_MODEL` 即可切换。

### 4. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开浏览器访问 `http://localhost:5173`。

## 使用流程

1. **上传 PRD** — 在首页上传 PDF 或 DOCX 格式的产品需求文档
2. **等待分析** — 系统自动执行 5 阶段分析流水线，实时显示进度
3. **查看图谱** — 在知识图谱页面浏览 PRD 的结构化拆解
4. **编辑画像** — 在虚拟用户页面查看和调整生成的用户画像
5. **查看叙事** — 浏览每个虚拟用户的操作场景仿真
6. **阅读报告** — 查看压测报告，了解盲区与瓶颈
7. **深度交互** — 通过 AI 对话深入探索产品问题

## 项目结构

```
virtual-user-lab/
├── frontend/                # React 前端
│   └── src/
│       ├── pages/           # 页面组件
│       ├── components/      # 通用组件
│       ├── store/           # Zustand 状态管理
│       ├── api/             # API 请求封装
│       └── hooks/           # 自定义 Hooks
├── backend/                 # FastAPI 后端
│   └── app/
│       ├── api/             # 路由 (upload, analysis, conversation, ws)
│       ├── llm/             # LLM 调用封装
│       ├── models/          # 数据库模型 & Pydantic Schema
│       ├── prompts/         # LLM Prompt 模板 (Chain 1-5)
│       ├── services/        # 核心业务逻辑 (pipeline, parser, etc.)
│       └── config.py        # 配置管理
├── docker-compose.yml       # PostgreSQL + Redis
├── .env.example             # 环境变量模板
└── README.md
```

## 配置说明

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key | （必填） |
| `ANTHROPIC_API_KEY` | Anthropic API Key（可选） | — |
| `LLM_MODEL` | LLM 模型标识 | `deepseek/deepseek-chat` |
| `LLM_TEMPERATURE` | 生成温度 | `0.7` |
| `DB_HOST` | PostgreSQL 主机 | `localhost` |
| `DB_PORT` | PostgreSQL 端口 | `5432` |
| `DB_NAME` | 数据库名称 | `vul` |
| `DB_USER` | 数据库用户名 | `postgres` |
| `DB_PASSWORD` | 数据库密码 | （必填） |
| `REDIS_HOST` | Redis 主机 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `MAX_UPLOAD_SIZE_MB` | 最大上传文件大小 | `10` |
| `MAX_CONCURRENT_ANALYSES` | 最大并发分析数 | `3` |

## 切换 LLM 模型

本项目使用 [LiteLLM](https://docs.litellm.ai/) 作为 LLM 网关，支持 100+ 模型。修改 `.env` 即可切换：

```env
# OpenAI
LLM_MODEL=gpt-4o
OPENAI_API_KEY=sk-xxx

# Anthropic Claude
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-xxx

# 其他模型参考 LiteLLM 文档
```

## License

MIT
