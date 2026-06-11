import os


class Settings:
    db_postgres_name = os.getenv("DB_POSTGRES_NAME", "ktra1_ai_db")
    db_postgres_user = os.getenv("DB_POSTGRES_USER", "postgres")
    db_postgres_password = os.getenv("DB_POSTGRES_PASSWORD", "123456")
    db_postgres_host = os.getenv("DB_POSTGRES_HOST", "postgres")
    db_postgres_port = os.getenv("DB_POSTGRES_PORT", "5432")

    database_url = os.getenv(
        "DATABASE_URL",
        (
            f"postgresql+psycopg2://{db_postgres_user}:{db_postgres_password}"
            f"@{db_postgres_host}:{db_postgres_port}/{db_postgres_name}"
        ),
    )

    neo4j_enabled = os.getenv("NEO4J_ENABLED", "true").lower() == "true"
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "12345678")

    rag_embed_dim = int(os.getenv("RAG_EMBED_DIM", "128"))
    product_service_url = os.getenv("PRODUCT_SERVICE_URL", "http://product-service:8003").rstrip("/")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "").rstrip("/")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1")

    weight_lstm = float(os.getenv("AI_WEIGHT_LSTM", "0.45"))
    weight_graph = float(os.getenv("AI_WEIGHT_GRAPH", "0.30"))
    weight_rag = float(os.getenv("AI_WEIGHT_RAG", "0.25"))


settings = Settings()
