from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API keys
    voyage_api_key: str = ""
    openai_api_key: str = ""

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "cdm_entities"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # OpenAI
    openai_model: str = "gpt-4o"

    # CDM data — set to local schemaDocuments path to skip GitHub fetching
    cdm_local_path: str = "../cdm-data/schemaDocuments"

    # Cosine similarity threshold above which graph traversal is triggered
    graph_threshold: float = 0.75


settings = Settings()
