# 🤖 AI 学习智能体系统 (Smart AI Learning Agent)

本项目是一个基于大语言模型（LLM）的全栈 AI 学习平台，主打 **“AI 闯关出题”** 与 **“智能学习建议”**。

项目在开源架构基础上进行 **二次开发与工程化重构**，围绕 RAG 检索精度、Agent 工具链扩展性以及系统的高可用降级策略持续改进。

> **当前发布状态**：本仓库保留当前工作区的修改。原有 AI 闯关、知识库和异步任务链路以及新增学习建议功能已存在；Rerank 尚未实现调用链路。以下保留所规划的核心改造方案，并逐项说明实际进度；目标能力不代表已经交付或通过效果评测。

## 🛠️ 技术栈

* **前端**：微信小程序、Taro、React、TypeScript
* **后端**：Python、FastAPI、Pydantic
* **大模型框架**：LangChain、LangGraph
* **AI 服务**：DeepSeek API、阿里云百炼（Embedding & Rerank，后者待接入）、Tavily 搜索
* **数据存储**：MySQL、ChromaDB

## 🚀 核心重构与架构亮点（我的核心贡献与改造目标）

### 1. 引入两阶段检索 (RAG + Rerank) 提升出题质量

**目标设计：**

* 针对原始单一向量检索容易引入“语义噪声”的问题，重构检索链路。
* 采用 **“粗排召回（Top-20） + 精排 Rerank（Top-3）”** 两阶段架构。
* 接入阿里云百炼 `gte-rerank` 模型，并基于 `asyncio.wait_for` 实现超时控制与自动降级：Rerank 失败时自动回退至普通向量检索。
* 通过控制最终切片数量减少无关上下文与 Token 消耗，目标是提升上下文相关性；收益需要对照评测，Rerank 本身也会增加调用成本和延迟。

**实际进度：** `backend/app/core/config.py` 已增加 Rerank 配置，但检索仍直接调用 `vector_store_service.similarity_search`，没有重排请求与降级实现。当前配置为召回 10、重排 4，模型名为 `gte_rerank`；正式接入时需调整为目标参数和有效模型名 `gte-rerank`。单次超时回退不等于具有故障计数与恢复探测的完整熔断器。

### 2. 扩展 Agentic RAG 工具链 (Function Calling)

* 自定义了 **“时间感知与学习建议工具”**，利用 Python `@tool` 装饰器并结合闭包机制，将时区配置固化，使模型无需传入时区参数。
* 设计了 **工具数据旁路回调机制（on_result）**，使工具获取的真实时间通过 Python 回调进入业务层；目标是直接返回给前端渲染，减少大模型对时间数据的“幻觉转述”。
* 新增了基于场景的 Agent System Prompt，通过规则与示例引导“时间查询”与“普通学习建议”的工具选择；是否调用工具仍由模型决策，路由准确率需要测试验证。

**实际进度：** 已新增 `backend/app/tools/learning_tools.py`、学习建议数据模型、Prompt 和 Service 草稿。后端未注册 `/api/v1/study/advice`，前端也未增加对应请求与展示；新增服务仍有命名错误和未完成分支，不能视为已交付功能。

### 3. 高可用与优雅降级设计

**目标设计：**

* **部分成功（Partial Success）兜底**：在 Service 层使用回调数组暂存工具执行结果，即使大模型因超时异常中断，仍能利用已获取的真实数据在 Python 端拼接出兜底学习建议，保障用户体验。
* **状态与数据分离**：返回给前端的 `Response` 包含 `degraded`（降级标识）和 `used_tools`（成功获取结果的工具列表），提升系统的可观测性。

**实际进度：** `StudyAdviceResponse` 已声明上述字段，但 `study_service.py` 的异常分支尚未返回兜底响应。现有服务还存在 `getlogger`、`onresult`、超时配置字段、最终消息索引和 `use_tools` 字段名不一致的问题，需要修复后再接通接口。

### 4. 异步并发与状态机（原有架构分析）

* 深入解析并保留 FastAPI + `asyncio.create_task` 的异步出题任务架构，前端通过返回 `Promise` 的定时轮询结合 `maxAttempts` 防死循环机制，缓解大模型长耗时导致的单次 HTTP 请求超时问题。
* 实际链路为 `POST /api/v1/quiz/generate/async` → 后台生成 → `GET /api/v1/quiz/task/{task_id}`，默认每 8 秒查询一次，最多 100 次。
* 该机制不等于任务不会超时；后台任务仍需进一步考虑进程重启与持久化恢复。

## 📁 目录结构

```text
├── backend/             # FastAPI 后端服务
│   ├── app/
│   │   ├── api/         # 路由层
│   │   ├── services/    # 业务逻辑（RAG、Agent、异步任务等）
│   │   ├── tools/       # 自定义 Agent 工具
│   │   ├── models/      # Pydantic 数据模型
│   │   ├── prompts/     # 大模型与 Agent 提示词
│   │   └── repositories/ # 数据库访问层
│   ├── tests/           # 后端测试
│   └── .env.example     # 环境变量示例，不含实际密钥
├── frontend/            # Taro + React 微信小程序前端
├── docs/                # 本地运行指南与上游项目说明
└── LICENSE              # MIT 许可证
```

## 本地运行与验证

克隆本仓库后，参考 [保姆级本地运行指南](docs/保姆级本地运行指南.md) 配置 Python、MySQL、前端依赖和 API 服务。指南来自上游项目，其中的克隆地址请替换为本仓库：

```bash
git clone https://github.com/JerryZhang-git49/smart-quiz-agent-system.git
cd smart-quiz-agent-system
```

后端进入 `backend` 创建虚拟环境，安装 `requirements.txt`，复制 `.env.example` 为 `.env` 并填写配置，然后运行 `python -m app.main`。前端进入 `frontend`，运行 `npm ci` 和 `npm run build:weapp`，通过微信开发者工具打开生成的小程序目录。

本次发布检查：

* 后端现有测试：`python -m pytest -q`，**139 项通过**。
* 前端微信小程序构建：`npm run build:weapp`，**通过**。
* Python 源码与测试语法检查：**78 个文件通过**。
* 以上检查未覆盖尚未接通的学习建议和 Rerank，不代表新增功能已经可用，也未验证真实外部 AI 服务的联调效果。

## 开源来源与许可

本项目基于 [liyupi/yu-ai-learn](https://github.com/liyupi/yu-ai-learn) 二次开发，保留原作者程序员鱼皮的版权声明及 [MIT 许可证](LICENSE)。

原始项目介绍与运行步骤保存在 [上游 README](docs/UPSTREAM_README.md)。上游已有的闯关、联网搜索、知识库、异步出题等能力与本仓库新增的学习工具和配置修改应分别理解。
