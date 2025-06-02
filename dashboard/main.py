# backend/app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager

# Placeholder for future startup/shutdown event logic (e.g., DB connection pool)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic:
    # print("FlipForce Backend Starting Up...")
    # Example: Initialize database connections, load ML models, etc.
    # await init_database() # Fictional function
    yield
    # Shutdown logic:
    # print("FlipForce Backend Shutting Down...")
    # Example: Close database connections, cleanup resources
    # await close_database_connections() # Fictional function

app = FastAPI(
    title="FlipForce API",
    description="API for the FlipForce trading card tracker and dashboard.",
    version="0.1.0",
    lifespan=lifespan  # Using the new lifespan context manager for startup/shutdown
)

# Import API routers here once they are created
# from .api.v1.routers import dashboard as dashboard_router_v1
# from .api.v1.routers import series as series_router_v1

# app.include_router(dashboard_router_v1.router, prefix="/api/v1/dashboard", tags=["v1_dashboard"])
# app.include_router(series_router_v1.router, prefix="/api/v1/series", tags=["v1_series"])

@app.get("/", tags=["Root"])
async def read_root():
    """
    Root endpoint for the FlipForce API.
    Provides a simple health check / welcome message.
    """
    return {"message": "Welcome to the FlipForce API!"}

# Optional: Add a health check endpoint
@app.get("/health", tags=["Health Check"])
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}

# To run this (after installing FastAPI and Uvicorn):
# uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# (Assuming your project root is one level above 'backend')