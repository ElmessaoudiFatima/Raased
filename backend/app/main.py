from fastapi import FastAPI

app = FastAPI(title="Raased API")

@app.get("/")
async def root():
    return {"status": "ok"}