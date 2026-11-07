from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .core import Base, engine
from .models import *  # noqa: F401,F403


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Airline Disruption Management Platform", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
