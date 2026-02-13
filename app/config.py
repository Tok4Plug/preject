"""
Configuração centralizada do sistema SaaS multi-tenant.
Suporta configuração dinâmica via banco de dados e ENV.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from functools import lru_cache
from enum import Enum

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Ambientes de execução."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DatabaseType(Enum):
    """Tipos de banco de dados suportados."""
    POSTGRES = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"


@dataclass
class DatabaseConfig:
    """Configuração de banco de dados por tenant."""
    url: str
    pool_size: int = 20
    max_overflow: int = 40
    pool_recycle: int = 3600
    pool_pre_ping: bool = True
    echo: bool = False
    
    @classmethod
    def from_env(cls, tenant_id: Optional[str] = None) -> 'DatabaseConfig':
        """Cria configuração a partir de variáveis de ambiente."""
        # Configuração multi-tenant: URLs por tenant
        if tenant_id:
            url_key = f"DATABASE_URL_{tenant_id.upper()}"
            url = os.getenv(url_key) or os.getenv("DATABASE_URL")
        else:
            url = os.getenv("DATABASE_URL")
        
        if not url:
            raise ValueError("DATABASE_URL não configurada")
        
        return cls(
            url=url,
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "40")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600")),
            pool_pre_ping=os.getenv("DB_POOL_PRE_PING", "true").lower() == "true",
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )


@dataclass
class RedisConfig:
    """Configuração do Redis para cache e filas."""
    url: str
    socket_timeout: int = 5
    socket_connect_timeout: int = 5
    retry_on_timeout: bool = True
    health_check_interval: int = 30
    
    @classmethod
    def from_env(cls) -> 'RedisConfig':
        url = os.getenv("REDIS_URL")
        if not url:
            raise ValueError("REDIS_URL não configurada")
        
        return cls(
            url=url,
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            socket_connect_timeout=int(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
            retry_on_timeout=os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true",
            health_check_interval=int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))
        )


@dataclass
class PaymentProviderConfig:
    """Configuração de provedores de pagamento."""
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    mercado_pago_access_token: Optional[str] = None
    pix_provider_url: Optional[str] = None
    pix_api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'PaymentProviderConfig':
        return cls(
            stripe_secret_key=os.getenv("STRIPE_SECRET_KEY"),
            stripe_webhook_secret=os.getenv("STRIPE_WEBHOOK_SECRET"),
            mercado_pago_access_token=os.getenv("MERCADO_PAGO_ACCESS_TOKEN"),
            pix_provider_url=os.getenv("PIX_PROVIDER_URL"),
            pix_api_key=os.getenv("PIX_API_KEY")
        )


@dataclass
class SecurityConfig:
    """Configuração de segurança."""
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    hmac_key: Optional[str] = None
    encryption_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        secret_key = os.getenv("SECRET_KEY")
        if not secret_key:
            raise ValueError("SECRET_KEY não configurada")
        
        return cls(
            secret_key=secret_key,
            algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
            access_token_expire_minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
            refresh_token_expire_days=int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")),
            hmac_key=os.getenv("HMAC_KEY"),
            encryption_key=os.getenv("ENCRYPTION_KEY")
        )


@dataclass
class TelemetryConfig:
    """Configuração de telemetria e observabilidade."""
    enable_metrics: bool = True
    enable_tracing: bool = True
    otlp_endpoint: Optional[str] = None
    prometheus_port: int = 9090
    log_level: str = "INFO"
    structured_logging: bool = True
    
    @classmethod
    def from_env(cls) -> 'TelemetryConfig':
        return cls(
            enable_metrics=os.getenv("ENABLE_METRICS", "true").lower() == "true",
            enable_tracing=os.getenv("ENABLE_TRACING", "true").lower() == "true",
            otlp_endpoint=os.getenv("OTLP_ENDPOINT"),
            prometheus_port=int(os.getenv("PROMETHEUS_PORT", "9090")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            structured_logging=os.getenv("STRUCTURED_LOGGING", "true").lower() == "true"
        )


@dataclass
class MultiBotConfig:
    """Configuração para suporte multi-bot."""
    bot_registry_table: str = "bots"
    max_bots_per_tenant: int = 100
    bot_token_rotation_days: int = 90
    default_flow: str = "main_flow"
    
    @classmethod
    def from_env(cls) -> 'MultiBotConfig':
        return cls(
            bot_registry_table=os.getenv("BOT_REGISTRY_TABLE", "bots"),
            max_bots_per_tenant=int(os.getenv("MAX_BOTS_PER_TENANT", "100")),
            bot_token_rotation_days=int(os.getenv("BOT_TOKEN_ROTATION_DAYS", "90")),
            default_flow=os.getenv("DEFAULT_FLOW", "main_flow")
        )


@dataclass
class SystemConfig:
    """Configuração principal do sistema."""
    environment: Environment
    debug: bool
    database: DatabaseConfig
    redis: RedisConfig
    payment_providers: PaymentProviderConfig
    security: SecurityConfig
    telemetry: TelemetryConfig
    multi_bot: MultiBotConfig
    
    # Configurações dinâmicas
    tenant_config_cache_ttl: int = 300  # 5 minutos
    feature_flags: Dict[str, bool] = field(default_factory=dict)
    rate_limits: Dict[str, int] = field(default_factory=dict)
    
    @classmethod
    @lru_cache(maxsize=1)
    def load(cls) -> 'SystemConfig':
        """Carrega configuração do sistema (singleton com cache)."""
        env = Environment(os.getenv("ENVIRONMENT", "production").lower())
        debug = os.getenv("DEBUG", "false").lower() == "true"
        
        # Carrega configurações dinâmicas
        feature_flags = json.loads(os.getenv("FEATURE_FLAGS", "{}"))
        rate_limits = json.loads(os.getenv("RATE_LIMITS", "{}"))
        
        return cls(
            environment=env,
            debug=debug,
            database=DatabaseConfig.from_env(),
            redis=RedisConfig.from_env(),
            payment_providers=PaymentProviderConfig.from_env(),
            security=SecurityConfig.from_env(),
            telemetry=TelemetryConfig.from_env(),
            multi_bot=MultiBotConfig.from_env(),
            tenant_config_cache_ttl=int(os.getenv("TENANT_CONFIG_CACHE_TTL", "300")),
            feature_flags=feature_flags,
            rate_limits=rate_limits
        )
    
    def get_tenant_database_config(self, tenant_id: str) -> DatabaseConfig:
        """Obtém configuração de banco de dados específica para um tenant."""
        return DatabaseConfig.from_env(tenant_id)
    
    def is_feature_enabled(self, feature_name: str, tenant_id: Optional[str] = None) -> bool:
        """Verifica se uma feature flag está habilitada."""
        # Primeiro verifica configuração por tenant
        if tenant_id:
            tenant_key = f"{feature_name}_{tenant_id}"
            if tenant_key in self.feature_flags:
                return self.feature_flags[tenant_key]
        
        # Fallback para configuração global
        return self.feature_flags.get(feature_name, False)
    
    def get_rate_limit(self, endpoint: str, tenant_id: Optional[str] = None) -> int:
        """Obtém rate limit para um endpoint específico."""
        # Rate limits podem ser por tenant
        if tenant_id:
            tenant_key = f"{endpoint}_{tenant_id}"
            if tenant_key in self.rate_limits:
                return self.rate_limits[tenant_key]
        
        # Fallback para rate limit global
        return self.rate_limits.get(endpoint, 100)  # Default: 100 requests por minuto


# Instância global de configuração
config = SystemConfig.load()


class DynamicConfigManager:
    """
    Gerenciador de configuração dinâmica por tenant.
    Permite alterações sem reinicialização do sistema.
    """
    
    def __init__(self):
        self._tenant_configs: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = config.tenant_config_cache_ttl
        
    async def get_tenant_config(self, tenant_id: str) -> Dict[str, Any]:
        """Obtém configuração dinâmica de um tenant."""
        # Verifica cache primeiro
        if tenant_id in self._tenant_configs:
            return self._tenant_configs[tenant_id]
        
        # Carrega do banco de dados (simulação)
        # Em produção, isso viria de uma tabela tenant_configs
        default_config = {
            "payment_methods": ["pix", "card", "boleto"],
            "default_currency": "BRL",
            "timezone": "America/Sao_Paulo",
            "locale": "pt_BR",
            "notifications_enabled": True,
            "antifraud_strictness": "medium"
        }
        
        self._tenant_configs[tenant_id] = default_config
        return default_config
    
    async def update_tenant_config(self, tenant_id: str, updates: Dict[str, Any]):
        """Atualiza configuração de um tenant dinamicamente."""
        current_config = await self.get_tenant_config(tenant_id)
        current_config.update(updates)
        
        # Em produção, persistiria no banco de dados
        # await self._persist_config(tenant_id, current_config)
        
        # Atualiza cache
        self._tenant_configs[tenant_id] = current_config
        logger.info(f"Configuração atualizada para tenant {tenant_id}")
    
    def invalidate_cache(self, tenant_id: Optional[str] = None):
        """Invalida cache de configuração."""
        if tenant_id:
            self._tenant_configs.pop(tenant_id, None)
        else:
            self._tenant_configs.clear()
        logger.info("Cache de configurações invalidado")


# Gerenciador global de configuração dinâmica
dynamic_config = DynamicConfigManager()