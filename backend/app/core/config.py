"""鱼皮AI闯关学习小程序 - 后端配置"""

from functools import lru_cache

from pydantic_settings import BaseSettings

from pydantic import Field


class Settings(BaseSettings):
    # 学习建议
    study_timezone: str = "Asia/Shanghai"
    study_advice_timeout_seconds : float = Field(
        default = 25.0,
        gt = 0,
        le = 60,
    )

    # Rerank
    enable_rerank: bool = False   # 是否启用 Rerank（重排序）功能。启用后，模型会对生成的题目进行排序，优先返回更符合用户需求的题目。

    # 第一阶段：向量召回数量
    kb_recall_k : int = Field(default = 10, gt = 0, le = 100)

    # 第二阶段：Rerank 之后的最终返回数量
    kb_rerank_k : int = Field(default = 4, gt = 0, le = 100)

    # Rerank模型
    rerank_model: str = "gte_rerank"

    # 百炼原生 Rerank 接口，不是 Embedding 的 compatible-mode 地址
    rerank_api_url: str = (
        "https://dashscope.aliyuncs.com"
        "/api/v1/services/rerank/text-rerank"
    )

    # 留空时使用现有 DASHSCOPE_API_KEY
    rerank_api_key: str = ""

    # 单次重排的总等待预算
    rerank_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=30,
    )

    # DeepSeek
    deepseek_api_key: str = "sk-xxx"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Tavily (Web Search)
    tavily_api_key: str = ""
    enable_web_search: bool = True

    # DashScope (百炼 Embedding，用于知识库 RAG)
    dashscope_api_key: str = ""
    dashscope_embedding_model: str = "text-embedding-v4"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # 知识库 / 向量存储
    chroma_persist_dir: str = "./data/chroma"
    kb_upload_dir: str = "./data/uploads"
    kb_max_documents_per_user: int = 10
    kb_max_file_size_mb: int = 10
    kb_chunk_size: int = 1000
    kb_chunk_overlap: int = 150
    kb_retrieve_top_k: int = 4

    # 题目配图（DashScope 千问-文生图 qwen-image）
    dashscope_image_model: str = "qwen-image-2.0"
    # 生图专用 API Key（留空时回退使用 dashscope_api_key）。
    # 注意：部分 sk-ws- 开头的工作空间 Key 按用途限定权限范围，Embedding 与生图可能需要各自的 Key。
    dashscope_image_api_key: str = ""
    # 图像生成使用的原生 DashScope API 地址（与 OpenAI 兼容模式的 dashscope_base_url 不同）
    # 留空时会自动从 dashscope_base_url 派生（将 /compatible-mode/v1 替换为 /api/v1）
    dashscope_image_base_url: str = ""
    image_gen_size: str = "512*512"
    image_gen_daily_limit: int = 20
    image_gen_max_concurrency: int = 5

    # 腾讯云 COS（用于持久化存储 AI 生成的题目配图）
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = ""
    cos_bucket: str = ""
    cos_upload_prefix: str = "quiz-images/"
    # 可选：自定义访问域名（如 CDN 加速域名），留空则使用 COS 默认域名
    cos_domain: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 43200  # 30 天

    # 微信小程序
    wechat_app_id: str = ""
    wechat_app_secret: str = ""

    # MySQL
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_database: str = "yu_ai_learn"
    mysql_charset: str = "utf8mb4"
    mysql_pool_minsize: int = 1
    mysql_pool_maxsize: int = 10
    mysql_auto_init: bool = True

    # Log
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
