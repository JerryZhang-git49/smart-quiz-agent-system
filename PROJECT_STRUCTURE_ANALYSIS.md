# yu-ai-learn 项目结构分析

## 1. 仓库概况

- **来源**：`https://github.com/liyupi/yu-ai-learn`
- **拥有者**：`liyupi`
- **默认分支**：`main`
- **当前拉取提交**：`d68cf0b`（2026-08-11，补充 README 中的 LangGraph 与 Harness Engineering 关键词）
- **许可证**：MIT
- **项目定位**：基于微信小程序的 AI 闯关学习产品。用户输入学习主题，系统联网或从私有文档检索资料，生成题库；用户完成答题后得到即时讲解和 AI 复盘报告。
- **规模**：约 150 个非 Git 文件，主要由 Python、TypeScript/TSX、Markdown 和测试文件组成。

## 2. 顶层目录

```text
ai_learning/
├─ backend/       FastAPI 后端、AI 编排、数据库访问、测试
├─ frontend/      Taro + React 微信小程序
├─ docs/          需求、方案、本地运行和用户系统文档
├─ openspec/      OpenSpec 规范与已归档变更
├─ prototypes/    Claude Code / Copilot 生成的页面原型
├─ .github/       OpenSpec 相关提示词和 Agent Skill
├─ README.md      产品介绍、技术选型、运行与部署说明
└─ LICENSE
```

## 3. 后端结构与职责

后端采用较标准的分层结构，入口为 `backend/app/main.py`。

```text
backend/app/
├─ api/v1/routes/       HTTP 路由：health、quiz、report、user、knowledge
├─ core/                配置、JWT 鉴权、MySQL 连接池、异常和敏感词过滤
├─ models/              Pydantic 请求/响应模型及领域数据结构
├─ llm/                 DeepSeek/LangChain 调用链和结构化输出
├─ prompts/             出题、报告、联网搜索、RAG Agent 的 Prompt
├─ services/            业务编排：出题、报告、搜索、RAG、文档、图片、用户
├─ repositories/        MySQL 持久化访问层
└─ utils/               ID 等通用工具
```

### 主要接口

| 路径 | 作用 | 鉴权 |
| --- | --- | --- |
| `GET /api/v1/health` | 健康检查 | 无 |
| `POST /api/v1/quiz/generate` | 同步生成题库 | 可选 |
| `POST /api/v1/quiz/generate/async` | 创建异步出题任务并返回 `task_id` | 可选 |
| `GET /api/v1/quiz/task/{task_id}` | 查询异步任务状态 | 无 |
| `POST /api/v1/report/generate` | 根据答题记录生成复盘报告 | 可选 |
| `POST /api/v1/user/login` | 微信 `jscode2session` 登录并签发 JWT | 无 |
| `GET/PUT /api/v1/user/profile` | 查询或更新用户资料 | 必选 |
| `GET /api/v1/user/quizzes` | 分页查询闯关历史 | 必选 |
| `GET /api/v1/user/quizzes/{quiz_id}` | 查看历史闯关详情 | 必选 |
| `POST/GET/DELETE /api/v1/knowledge/documents...` | 上传、查询、删除知识库文档 | 必选 |

### 出题链路

1. 前端调用异步出题接口，后端生成 `task_id` 并通过 `asyncio.create_task` 启动后台任务。
2. 若提供 `doc_id`，服务层校验用户归属和文档状态，然后走 Chroma 向量检索；否则走 Tavily 搜索 Agent。
3. LangGraph ReAct Agent 负责决定搜索、提取或知识库检索动作，得到参考上下文。
4. LangChain + DeepSeek 根据 Prompt 和 Pydantic Schema 生成结构化题库。
5. 可选调用阿里云百炼文生图；生成图片后上传腾讯云 COS。图片失败不会阻断题库生成。
6. 已登录用户将题库写入 MySQL，任务状态更新为 `completed`，前端轮询获取结果。

### 复盘与持久化链路

用户在小程序端本地即时判题，完成整组题目后提交答题记录。后端计算基础得分并调用 DeepSeek 生成报告；已登录时写入 `answer_records`、`reports` 并增加 XP。历史详情由多个表联合读取。

### 知识库 RAG 链路

支持 PDF、DOCX、Markdown、TXT。上传后先写入本地文件和 `kb_documents`，后台解析并用递归文本分块器切分，再通过 DashScope Embedding 写入按用户隔离的 Chroma collection。删除文档时同时删除数据库记录和向量；出题时按 `user_id + doc_id` 过滤检索结果。

### 数据库表

应用启动时 `backend/app/core/db.py` 会自动初始化 7 张表：`users`、`quiz_sessions`、`answer_records`、`reports`、`quiz_tasks`、`kb_documents`、`image_generation_logs`。仓库内的 `backend/sql/init_mysql.sql` 只覆盖基础表，README 已提示不要用它替代自动初始化，否则会缺少任务、知识库和图片日志表。

## 4. 前端结构与页面流

`frontend` 是 Taro 4 + React 18 + TypeScript + Sass 项目，目标平台是微信小程序，也保留 H5 构建配置。

```text
frontend/src/
├─ app.ts / app.config.ts     应用启动和页面、TabBar 配置
├─ pages/index                首页：输入主题、启动生成、查看最近记录
├─ pages/quiz                 闯关：单选/多选/判断、本地判题、即时讲解
├─ pages/report               报告：正确率、薄弱点、总结、建议和题目回顾
├─ pages/profile              个人中心：资料、XP、历史闯关
├─ pages/knowledge            知识库：上传、处理状态、删除、基于文档出题
├─ services/api.ts            API 封装、JWT 本地缓存、任务轮询和类型定义
└─ assets/                    TabBar 图标
```

页面主流程为：`首页输入 → 创建异步任务 → 轮询状态 → 闯关页 → 报告页 → 个人中心历史回看`。开发环境 API 指向 `http://localhost:8000/api/v1`，生产环境配置指向 `https://ai-learn.codefather.cn/api/v1`。

## 5. 外部依赖与运行边界

- **必需**：Python 3.11+、Node.js 18+、MySQL 8+、DeepSeek API Key。
- **可选能力**：Tavily 联网搜索、阿里云百炼 Embedding/文生图、腾讯云 COS、微信小程序 AppID/AppSecret。
- **部署**：后端提供 Python 3.11 多阶段 Dockerfile，默认适配微信云托管，监听 `PORT`（默认 80）。
- **测试**：`backend/tests` 有约 83 个测试函数，覆盖 API、模型、鉴权、搜索/RAG、文档处理、向量存储、图片服务和仓储层；大量第三方调用通过 mock 隔离。
- **运行命令**：后端使用 `uvicorn app.main:app --reload`，前端使用 `npm run dev:weapp`，微信开发者工具打开 `frontend/dist`。

## 6. 工程优点

1. 业务边界比较清晰：路由、服务、仓储、模型和 LLM 调用分层，便于替换模型或存储实现。
2. AI 输出使用 Pydantic 结构化 Schema，Prompt、模型工厂和业务校验分开，降低前端解析不稳定的风险。
3. 既支持公开知识的联网搜索，又支持用户私有文档 RAG，并用用户和文档 ID 做检索隔离。
4. 长耗时出题采用异步任务 + 前端轮询，避免请求超时；生图失败也不会影响核心出题流程。
5. 文档、原型、OpenSpec 变更和测试较完整，适合作为 AI 应用全流程教学项目。

## 7. 当前需要留意的风险

1. **异步任务是进程内任务**：`asyncio.create_task` 在服务重启或多实例部署时可能丢失；生产环境应改为持久化队列或独立任务 worker。
2. **任务查询没有用户鉴权**：`GET /quiz/task/{task_id}` 可凭任务 ID 查询结果。任务 ID 随机性较高，但若需要严格隔离，应校验登录用户与任务归属。
3. **默认安全配置不能直接用于生产**：JWT Secret、MySQL 默认密码和 DeepSeek 示例值都在配置类中提供了默认值，部署时必须通过环境变量覆盖；同时应收紧 CORS。
4. **前端通过路由参数传递完整题库和答题记录**：题量或内容变长时可能触及小程序 URL 长度限制，也会增加页面状态和敏感数据暴露面。
5. **报告接口接收客户端答题结果**：当前设计适合轻量学习体验，但如果 XP 或成绩具有强约束，应在服务端保存题库并重新判分，避免客户端篡改。
6. **搜索、Embedding、生图和 COS 都依赖外部服务**：需要配置超时、重试、额度监控和降级策略；目前部分功能已有超时/失败兜底，但仍需关注成本和并发。
7. **敏感词过滤是简单关键词匹配**：只能作为 MVP 级别的初筛，不能替代正式的内容安全服务。

## 8. 建议的阅读和开发顺序

1. 先读 `README.md`、`docs/需求分析文档.md` 和 `docs/方案设计文档.md`，理解产品闭环和技术决策。
2. 从 `frontend/src/pages/index/index.tsx` 与 `frontend/src/services/api.ts` 跟踪用户发起出题和轮询。
3. 再看 `backend/app/api/v1/routes/quiz.py` → `services/quiz_service.py` → `services/search_service.py` / `rag_service.py` → `llm/quiz_chain.py`。
4. 继续阅读 `report_service.py`、`quiz_repository.py` 和 `user_repository.py`，理解报告落库、XP 和历史回看。
5. 最后阅读 `knowledge_service.py`、`document_loader_service.py`、`vector_store_service.py` 以及对应测试，掌握 RAG 扩展点。

