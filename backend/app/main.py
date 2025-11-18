from fastapi import FastAPI
from app.api import messages, deals

app = FastAPI(title="CapReSol API")

app.include_router(messages.router)
app.include_router(deals.router)


@app.get("/")
def root():
    return {"message": "CapReSol backend is running"}
