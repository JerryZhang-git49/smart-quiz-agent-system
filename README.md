# 🤖 AI 学习智能体系统 (Smart AI Learning Agent)

本项目是一个基于大语言模型（LLM）的全栈 AI 学习平台，主打 **“AI 闯关出题”** 与 **“智能学习建议”**。

项目在开源架构基础上进行 **二次开发与工程化重构**，围绕 RAG 检索精度、Agent 工具链扩展性以及系统的高可用降级策略持续改进。

> **当前开发状态**：学习建议和两阶段检索已完成前后端接入，并增加工具调用、超时、异常响应和降级的自动化测试。Rerank 默认关闭，按下方说明配置后启用。本地测试使用模拟模型及 HTTP 响应，真实 AI 服务的权限、效果与延迟仍需配置后联调。
> 
> **当前发布状态**：本仓库保留当前工作区的修改。原有 AI 闯关、知识库和异步任务链路以及新增学习建议功能已存在；Rerank 尚未实现调用链路。以下保留所规划的核心改造方案，并逐项说明实际进度；目标能力不代表已经交付或通过效果评测。


## 🛠️ 技术栈

* **前端**：微信小程序、Taro、React、TypeScript
* **后端**：Python、FastAPI、Pydantic
* **大模型框架**：LangChain、LangGraph
* **AI 服务**：DeepSeek API、阿里云百炼（Embedding & Rerank）、Tavily 搜索
* **数据存储**：MySQL、ChromaDB

## 🚀 核心重构与架构亮点（我的核心贡献）

### 1. 引入两阶段检索 (RAG + Rerank) 提升出题质量

**已实现：**

* 针对原始单一向量检索容易引入“语义噪声”的问题，重构检索链路。
* 采用 **“粗排召回（Top-20） + 精排 Rerank（Top-3）”** 两阶段架构。
* 接入阿里云百炼 `gte-rerank` 模型，并基于 `asyncio.wait_for` 实现超时控制与自动降级：Rerank 失败时自动回退至普通向量检索。
* 通过控制最终切片数量减少无关上下文与 Token 消耗，目标是提升上下文相关性；收益需要对照评测，Rerank 本身也会增加调用成本和延迟。

**代码入口：** `rag_service.py` 的异步知识库工具调用 `retrieval_service.py`，在限定用户和文档的 Chroma 结果上执行 `rerank_service.py`。默认召回 20、保留 3；按返回索引选取原始 Document，保留页码等元数据。未配置 Key、API 超时、HTTP 失败、重复/越界索引、非有限分数、结果不足或格式错误均会回退至原向量 Top-3，不重复召回。关闭开关时保留原 Top-4 行为。单次超时回退不等于具有故障计数与恢复探测的完整熔断器。

### 2. 扩展 Agentic RAG 工具链 (Function Calling)

* 自定义了 **“时间感知与学习建议工具”**，利用 Python `@tool` 装饰器并结合闭包机制，将时区配置固化，使模型无需传入时区参数。
* 实现 **工具数据旁路回调机制（on_result）**，使工具获取的真实时间通过 Python 回调进入业务层，直接返回给前端渲染，减少大模型对时间数据的“幻觉转述”。
* 新增了基于场景的 Agent System Prompt，通过规则与示例引导“时间查询”与“普通学习建议”的工具选择；是否调用工具仍由模型决策，路由准确率需要测试验证。

**使用入口：** 首页输入“现在几点了？我想再学一会儿 Python”，点击“获取学习建议”。`POST /api/v1/study/advice` 通过 LangGraph ReAct Agent 调用时间工具，返回建议、工具读取的带时区时间及成功工具列表。普通学习方法问题可不调用时间工具。时间工具使用异步函数，回调在请求事件循环中完成，不经过模型重新解析。

### 3. 高可用与优雅降级设计

**已实现：**

* **部分成功（Partial Success）兜底**：在 Service 层使用回调数组暂存工具执行结果，即使大模型因超时异常中断，仍能利用已获取的真实数据在 Python 端拼接出兜底学习建议，保障用户体验。
* **状态与数据分离**：返回给前端的 `Response` 包含 `degraded`（降级标识）和 `used_tools`（成功获取结果的工具列表），提升系统的可观测性。

**响应行为：** 模型默认最多等待 25 秒；构建失败、超时或无有效最终回复时返回 `degraded=true` 的备用建议。工具已读取成功时保留 `clock` 和 `used_tools`；没有真实时间时返回 `clock=null`，不伪造当前时间。工具本身失败也会标记降级。前端展示查询时刻、时区和备用建议提示，`used_tools` 保留在接口数据中供排查。

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

### 新增功能配置

在 `backend/.env` 添加以下配置后重启后端（完整参数见 `.env.example`）：

```dotenv
STUDY_TIMEZONE=Asia/Shanghai
STUDY_ADVICE_TIMEOUT_SECONDS=25
ENABLE_RERANK=true
KB_RECALL_K=20
KB_RERANK_K=3
RERANK_MODEL=gte-rerank
RERANK_TIMEOUT_SECONDS=3
```

Rerank 使用百炼原生接口，需要开通对应模型并提供 `RERANK_API_KEY`；留空时使用 `DASHSCOPE_API_KEY`。`ENABLE_RERANK=false` 时仅用原向量检索。学习建议独立于 Tavily 开关，不需要联网搜索 Key。

知识库页面点击“开始闯关”后，可以在弹窗中输入学习重点（最多 500 字），留空则综合出题。检索片段会带上文档 ID 和页码，页码未知时明确标记。

### 自动化验证

* 后端：在 `backend` 运行 `python -m pytest -q`。
* 前端类型：在 `frontend` 运行 `npx tsc --noEmit`。
* 小程序构建：在 `frontend` 运行 `npm run build:weapp`。
* 新增测试覆盖真实 LangGraph 图配合假模型的工具调用、时区换算、部分成功后超时、备用建议、请求校验、百炼请求协议、错误响应、总等待超时、Top-20 → Top-3、文档元数据保留和重排回退。测试不调用收费 AI 服务，尚未进行真实服务质量对照评测。

## 开源来源与许可

本项目基于 [liyupi/yu-ai-learn](https://github.com/liyupi/yu-ai-learn) 二次开发，保留原作者程序员鱼皮的版权声明及 [MIT 许可证](LICENSE)。

原始项目介绍与运行步骤保存在 [上游 README](docs/UPSTREAM_README.md)。上游已有的闯关、联网搜索、知识库、异步出题等能力与本仓库新增的学习工具和配置修改应分别理解。
