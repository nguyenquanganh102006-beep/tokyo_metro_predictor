from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, pathfinding, admin, stations
from app.core.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Tokyo Subway Pathfinder API",
    description="Tìm đường tàu điện ngầm Tokyo",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,         prefix="/api/auth",         tags=["Auth"])
app.include_router(pathfinding.router,  prefix="/api/path",         tags=["Pathfinding"])
app.include_router(admin.router,        prefix="/api/admin",        tags=["Admin"])
app.include_router(stations.router,     prefix="/api/stations",     tags=["Stations"])

@app.get("/")
def root():
    return {"message": "Tokyo Subway API is running"}
