from fastapi import FastAPI

from .api import router
from .background_tasks import initialize_scheduler, shutdown_scheduler
from .container import container
from .database import db_manager


def create_app() -> FastAPI:
    app = FastAPI(title="AI Service", version="5.0.0")
    app.include_router(router)

    @app.on_event("startup")
    def startup_event() -> None:
        db_manager.create_tables()
        initialize_scheduler()

    @app.on_event("shutdown")
    def shutdown_event() -> None:
        shutdown_scheduler()
        container.graph.close()

    return app
