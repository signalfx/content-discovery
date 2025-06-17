from fastapi import FastAPI
from app.routers import bits

app = FastAPI(title="Bits API")

app.include_router(bits.router, prefix="/api/bits")
