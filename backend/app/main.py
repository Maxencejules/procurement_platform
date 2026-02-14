from contextlib import asynccontextmanager
from uuid import UUID

import strawberry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.auth.jwt import decode_token
from app.auth.rbac import AuthContext
from app.database import engine, Base, async_session
from app.metrics import PrometheusMiddleware, metrics_endpoint
from app.schema.queries import Query
from app.schema.mutations import Mutation

# Import models so they register with Base
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


schema = strawberry.Schema(query=Query, mutation=Mutation)


async def get_context(request: Request) -> dict:
    session = async_session()
    ctx = {"session": session, "auth": None}

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_token(token)
        if payload:
            ctx["auth"] = AuthContext(
                user_id=payload["sub"],
                org_id=payload["org_id"],
                role=payload["role"],
            )
    return ctx


graphql_router = GraphQLRouter(schema, context_getter=get_context)

app = FastAPI(title="Procurement Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(PrometheusMiddleware)

app.include_router(graphql_router, prefix="/graphql")
app.add_route("/metrics", metrics_endpoint)


@app.get("/health")
async def health():
    return {"status": "ok"}
