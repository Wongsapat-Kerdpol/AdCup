from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import (
    admin,
    admin_submissions,
    auth,
    campaign_manage,
    campaigns,
    duplicates,
    outlook,
    payments,
    review,
    settlement,
    submissions,
    youtube,
)
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_on_startup:
        seed_if_empty()
    yield


app = FastAPI(title="AdCup API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Main
app.include_router(auth.router)
app.include_router(campaigns.router)
app.include_router(outlook.router)
app.include_router(duplicates.router)  # anti-fraud: duplicate-clip warnings
app.include_router(admin_submissions.router)  # admins: who submitted what, per campaign
# Person 1
app.include_router(campaign_manage.router)
# Person 2
app.include_router(submissions.router)
app.include_router(review.router)
app.include_router(settlement.router)
# Person 3
app.include_router(youtube.router)
app.include_router(payments.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
