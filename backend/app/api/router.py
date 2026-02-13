from fastapi import APIRouter

from app.api import (
    agents,
    auth,
    bindings,
    bots,
    health,
    knowledge_bases,
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
