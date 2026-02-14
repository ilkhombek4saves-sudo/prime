from fastapi import APIRouter

from app.api import (
    agents,
    auth,
    bindings,
    bots,
    health,
    knowledge_bases,
    node_executions,
    onboard,
    organizations,
    pairing,
    plugins,
    providers,
    sessions,
    settings,
    tasks,
    users,
    ws,
)
from app.gateway.webchat import router as webchat_router
from app.api.analytics import router as analytics_router
from app.api.memory import router as memory_router
from app.api.cron import router as cron_router
from app.api.webhooks import router as webhooks_router
from app.api.skills import router as skills_router
from app.api.tailscale import router as tailscale_router
from app.api.doctor import router as doctor_router
from app.api.security import router as security_router

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(bots.router)
api_router.include_router(agents.router)
api_router.include_router(bindings.router)
api_router.include_router(pairing.router)
api_router.include_router(providers.router)
api_router.include_router(plugins.router)
api_router.include_router(sessions.router)
api_router.include_router(tasks.router)
api_router.include_router(users.router)
api_router.include_router(settings.router)
api_router.include_router(knowledge_bases.router)
api_router.include_router(organizations.router)
api_router.include_router(ws.router)
api_router.include_router(webchat_router)
api_router.include_router(analytics_router)
api_router.include_router(memory_router)
api_router.include_router(cron_router)
api_router.include_router(webhooks_router)
api_router.include_router(skills_router)
api_router.include_router(tailscale_router)
api_router.include_router(doctor_router)
api_router.include_router(security_router)
api_router.include_router(node_executions.router)
api_router.include_router(onboard.router)
