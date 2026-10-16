import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
from .config import settings
from .routers import auth, imports, students, drives, institution, learning, evidence, insights, bootstrap, campus, campus_life, fees
from .middleware import BoundedBodyMiddleware


@asynccontextmanager
async def lifespan(app):
    async def reminders():
        from .campus_services import automatic_tick

        while True:
            await asyncio.sleep(max(30, settings().automation_interval_seconds))
            try:
                await asyncio.to_thread(automatic_tick)
            except Exception:
                # No document content, payment secrets or student data enters logs.
                logging.getLogger("campusmind.automation").warning("Campus reminder sweep failed; will retry next interval.")

    task = asyncio.create_task(reminders()) if settings().automation_enabled and not settings().testing else None
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="CampusMind AI",
    version="0.2.0",
    description="Tenant-isolated CollegeOps, Campus Hub and PlacementOS. No LLM required.",
    lifespan=lifespan,
)
app.add_middleware(BoundedBodyMiddleware)


@app.middleware("http")
async def protections(request: Request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin != settings().app_origin:
            return JSONResponse({"detail": "Origin is not allowed."}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Cross-site requests are not allowed."}, status_code=403)
        length = request.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > 10 * 1024 * 1024):
            return JSONResponse({"detail": "Request exceeds the 10 MB limit."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(IntegrityError)
async def conflict_handler(request, exc):
    return JSONResponse({"detail": "This record conflicts with existing data. Refresh and check the unique fields."}, status_code=409)


@app.exception_handler(RequestValidationError)
async def validation_handler(request, exc):
    return JSONResponse(
        {"detail": "; ".join(f"{'.'.join(str(p) for p in e['loc'][1:])}: {e['msg']}" for e in exc.errors())}, status_code=422
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "phase": 2, "ai_required": False}


for router in (
    auth.router,
    imports.router,
    students.router,
    drives.router,
    institution.router,
    learning.router,
    evidence.router,
    insights.router,
    bootstrap.router,
    campus.router,
    campus_life.router,
    fees.router,
):
    app.include_router(router, prefix="/api")
