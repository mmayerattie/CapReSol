from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "CapReSol backend is running"}
