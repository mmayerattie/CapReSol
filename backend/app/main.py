from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import messages, deals, analyses, analytics, auth, ml, notary
from app.config import settings

app = FastAPI(title="CapReSol API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(messages.router)
app.include_router(deals.router)
app.include_router(analyses.router)
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(ml.router)
app.include_router(notary.router)


@app.get("/")
def root():
    return {"message": "CapReSol backend is running"}
