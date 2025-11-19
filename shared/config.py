"""
Shared configuration module using Pydantic Settings.
Provides type-safe configuration with environment variable overrides.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    """PostgreSQL database configuration."""
    model_config = SettingsConfigDict(env_prefix="POSTGRES_")
    
    host: str = "localhost"
    port: int = 5432
    db: str = "recommendation_db"
    user: str = "recommendation_user"
    password: str = "recommendation_pass"
    ssl_mode: str = "disable"
    
    @property
    def connection_string(self) -> str:
        """Get PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}?sslmode={self.ssl_mode}"


class MongoDBConfig(BaseSettings):
    """MongoDB configuration."""
    model_config = SettingsConfigDict(env_prefix="MONGODB_")
    
    host: str = "localhost"
    port: int = 27017
    db: str = "recommendation_events"
    user: str = "recommendation_user"
    password: str = "recommendation_pass"
    
    @property
    def connection_string(self) -> str:
        """Get MongoDB connection string."""
        if self.user and self.password:
            return f"mongodb://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}?authSource=admin"
        return f"mongodb://{self.host}:{self.port}/{self.db}"


class RedisConfig(BaseSettings):
    """Redis configuration."""
    model_config = SettingsConfigDict(env_prefix="REDIS_")
    
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    ttl_seconds: int = 3600


class KafkaConfig(BaseSettings):
    """Kafka/Redpanda configuration."""
    model_config = SettingsConfigDict(env_prefix="KAFKA_")
    
    brokers: str = "localhost:9092"
    topic_events: str = "user-events"
    topic_features: str = "user-features"
    consumer_group: str = "stream-processor"


class MLflowConfig(BaseSettings):
    """MLflow configuration."""
    model_config = SettingsConfigDict(env_prefix="MLFLOW_")
    
    tracking_uri: str = "http://localhost:5000"
    experiment_name: str = "recommendation-system"


class VectorDBConfig(BaseSettings):
    """Vector database configuration (Pinecone or FAISS)."""
    use_pinecone: bool = False
    pinecone_api_key: Optional[str] = None
    pinecone_environment: str = "us-west1-gcp"
    pinecone_index_name: str = "recommendation-vectors"
    faiss_index_path: str = "./data/faiss_index"
    faiss_dimension: int = 128


class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # Service configuration
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Feature store
    feature_ttl_seconds: int = 3600
    feature_batch_size: int = 100
    enable_exactly_once: bool = False
    
    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    circuit_breaker_half_open_max_calls: int = 3
    
    # Sub-configurations
    database: DatabaseConfig = DatabaseConfig()
    mongodb: MongoDBConfig = MongoDBConfig()
    redis: RedisConfig = RedisConfig()
    kafka: KafkaConfig = KafkaConfig()
    mlflow: MLflowConfig = MLflowConfig()
    vector_db: VectorDBConfig = VectorDBConfig()


# Global settings instance
settings = Settings()

