from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import messages, deals, analyses

app = FastAPI(title="CapReSol API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router)
app.include_router(deals.router)
app.include_router(analyses.router)


@app.get("/")
def root():
    return {"message": "CapReSol backend is running"}
