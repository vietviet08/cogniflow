from fastapi import APIRouter

from app.api.routes import (
    auth,
    chat,
    health,
    insights,
    integrations,
    intelligence,
    jobs,
    organizations,
    processing,
    projects,
    provider_settings,
    query,
    reports,
    reviews,
    runs,
    saved_searches,
    share_links,
    sources,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(projects.router, tags=["projects"])
api_router.include_router(intelligence.router, tags=["intelligence"])
api_router.include_router(integrations.router, tags=["integrations"])
api_router.include_router(integrations.oauth_router, tags=["integrations"])
api_router.include_router(provider_settings.router, tags=["providers"])
api_router.include_router(sources.router, tags=["sources"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(processing.router, tags=["processing"])
api_router.include_router(query.router, tags=["query"])
api_router.include_router(insights.router, tags=["insights"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(reviews.router, tags=["reviews"])
api_router.include_router(runs.router, tags=["runs"])
api_router.include_router(saved_searches.router, tags=["saved-searches"])
api_router.include_router(share_links.router, tags=["share-links"])
api_router.include_router(share_links.public_router, tags=["public"])
api_router.include_router(organizations.router, tags=["organizations"])
