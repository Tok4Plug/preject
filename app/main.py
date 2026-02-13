"""
Ponto de entrada principal do sistema SaaS multi-bot.
Responsável pela inicialização dinâmica de todos os componentes.
"""
import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Dict, List

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.healthcheck_engine import HealthcheckEngine
from app.database import init_db, shutdown_db
from app.handlers.telegram_bot import MultiBotManager
from app.queue.base import QueueManager
from app.utils.cryptography import CryptoManager

# Configuração de logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    """
    # Startup
    logger.info("app_starting", environment=settings.ENVIRONMENT)
    
    try:
        # Inicializa criptografia
        CryptoManager.initialize(settings.CRYPTO_SECRET_KEY)
        
        # Inicializa banco de dados
        await init_db()
        
        # Inicializa gerenciador de filas
        await QueueManager.initialize()
        
        # Inicializa gerenciador multi-bot
        bot_manager = MultiBotManager()
        await bot_manager.initialize_all_bots()
        
        # Inicializa Healthcheck Engine
        health_engine = HealthcheckEngine()
        await health_engine.initialize()
        
        # Adiciona instâncias ao state do app
        app.state.bot_manager = bot_manager
        app.state.queue_manager = QueueManager
        app.state.health_engine = health_engine
        
        # Configura handlers de shutdown
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
        
        logger.info("app_started_successfully")
        yield
        
    except Exception as e:
        logger.error("app_startup_failed", error=str(e), exc_info=True)
        raise
        
    finally:
        # Shutdown
        logger.info("app_shutting_down")
        await shutdown()


async def shutdown():
    """
    Processo de shutdown gracioso.
    """
    logger.info("initiating_graceful_shutdown")
    
    # Para todos os bots
    if hasattr(app.state, 'bot_manager'):
        await app.state.bot_manager.shutdown_all_bots()
    
    # Para workers das filas
    if hasattr(app.state, 'queue_manager'):
        await app.state.queue_manager.shutdown()
    
    # Fecha conexões do banco
    await shutdown_db()
    
    logger.info("shutdown_completed")


# Inicializa app FastAPI com lifespan
app = FastAPI(
    title="SaaS Multi-Bot Platform",
    description="Plataforma SaaS modular para gestão multi-bot, pagamentos e controle de acesso",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)


# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TenantMiddleware:
    """
    Middleware para extrair e validar tenant ID de todas as requisições.
    """
    async def __call__(self, request: Request, call_next):
        # Extrai tenant ID do header ou do path
        tenant_id = request.headers.get("X-Tenant-ID") or request.query_params.get("tenant_id")
        
        if not tenant_id and request.url.path.startswith("/api/"):
            # Para APIs, requer tenant ID
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Tenant ID is required"}
            )
        
        # Adiciona tenant_id ao request state
        request.state.tenant_id = tenant_id
        
        # Log estruturado
        logger.info(
            "request_received",
            path=request.url.path,
            method=request.method,
            tenant_id=tenant_id,
            client_ip=request.client.host if request.client else None
        )
        
        response = await call_next(request)
        
        logger.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            tenant_id=tenant_id
        )
        
        return response


# Adiciona middleware de tenant
app.middleware("http")(TenantMiddleware())


# Exception handlers globais
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Handler global de exceções.
    """
    error_id = CryptoManager.generate_uuid()
    
    logger.error(
        "unhandled_exception",
        error_id=error_id,
        path=request.url.path,
        method=request.method,
        tenant_id=getattr(request.state, 'tenant_id', None),
        error_type=type(exc).__name__,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error_id": error_id,
            "detail": "Internal server error",
            "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    )


# Endpoints de sistema
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint para Kubernetes e load balancers.
    """
    if hasattr(app.state, 'health_engine'):
        health_status = await app.state.health_engine.check_all()
        if all(status["status"] == "healthy" for status in health_status.values()):
            return {"status": "healthy", "services": health_status}
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unhealthy", "services": health_status}
            )
    return {"status": "healthy"}


@app.get("/ready", tags=["System"])
async def readiness_check():
    """
    Readiness check para verificar se a aplicação está pronta para receber tráfego.
    """
    checks = {}
    
    # Verifica banco de dados
    try:
        # Tenta uma query simples
        from app.database import database
        await database.execute("SELECT 1")
        checks["database"] = "ready"
    except Exception as e:
        checks["database"] = f"not_ready: {str(e)}"
    
    # Verifica filas
    if hasattr(app.state, 'queue_manager'):
        try:
            await app.state.queue_manager.ping()
            checks["queues"] = "ready"
        except Exception as e:
            checks["queues"] = f"not_ready: {str(e)}"
    
    # Verifica bots
    if hasattr(app.state, 'bot_manager'):
        bots_status = await app.state.bot_manager.get_status()
        checks["bots"] = bots_status
    
    if all("ready" in str(v) for v in checks.values()):
        return {"status": "ready", "checks": checks}
    else:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks}
        )


@app.get("/metrics", tags=["System"])
async def metrics_endpoint():
    """
    Endpoint de métricas para Prometheus.
    """
    from app.core.metrics_engine import MetricsEngine
    metrics = await MetricsEngine.get_all_metrics()
    return metrics


# Endpoint para webhooks de pagamento
@app.post("/webhooks/payment/{provider}", tags=["Webhooks"])
async def payment_webhook(provider: str, request: Request):
    """
    Endpoint para receber webhooks de todos os providers de pagamento.
    """
    from app.handlers.webhook_handler import PaymentWebhookHandler
    
    # Extrai raw body
    raw_body = await request.body()
    headers = dict(request.headers)
    
    # Processa webhook
    handler = PaymentWebhookHandler()
    result = await handler.process(
        provider=provider,
        raw_body=raw_body,
        headers=headers,
        signature=headers.get("x-signature")
    )
    
    if result["success"]:
        return {"status": "processed", "event_id": result["event_id"]}
    else:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "error", "detail": result["error"]}
        )


# API Admin (protegida)
@app.get("/admin/bots", tags=["Admin"])
async def list_bots(request: Request):
    """
    Lista todos os bots registrados (requer autenticação admin).
    """
    # Verifica token admin
    auth_token = request.headers.get("Authorization")
    if not auth_token or not auth_token.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid authorization token"}
        )
    
    token = auth_token.replace("Bearer ", "")
    if token != settings.ADMIN_API_TOKEN:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid admin token"}
        )
    
    from app.models.bot import Bot
    bots = await Bot.get_all_active()
    return {"bots": [bot.to_dict() for bot in bots]}


@app.post("/admin/bots/register", tags=["Admin"])
async def register_bot(request: Request):
    """
    Registra um novo bot dinamicamente.
    """
    # Verifica token admin
    auth_token = request.headers.get("Authorization")
    if not auth_token or not auth_token.startswith("Bearer "):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing or invalid authorization token"}
        )
    
    token = auth_token.replace("Bearer ", "")
    if token != settings.ADMIN_API_TOKEN:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Invalid admin token"}
        )
    
    data = await request.json()
    
    from app.models.bot import Bot
    from app.handlers.telegram_bot import MultiBotManager
    
    try:
        # Cria bot no banco
        bot = await Bot.create(
            name=data["name"],
            token_hash=CryptoManager.hash_token(data["token"]),
            platform="telegram",
            default_flow=data.get("default_flow", "main_flow"),
            config=data.get("config", {}),
            status="active"
        )
        
        # Inicializa bot dinamicamente
        if hasattr(app.state, 'bot_manager'):
            await app.state.bot_manager.initialize_bot(bot.id, data["token"])
        
        logger.info("bot_registered_dynamically", bot_id=bot.id, bot_name=bot.name)
        
        return {"status": "registered", "bot": bot.to_dict()}
        
    except Exception as e:
        logger.error("bot_registration_failed", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
        log_config=None,  # Usa structlog configurado
        access_log=False  # Já temos logging estruturado
    )