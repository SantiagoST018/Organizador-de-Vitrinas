from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routes.api import router


BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_FILE = BASE_DIR / "frontend" / "consola-vitrinas-visual.html"


app = FastAPI(
    title="Organizador de Vitrinas PE",
    version="1.0.0"
)

app.include_router(router)


@app.get("/")
def inicio():
    return FileResponse(FRONTEND_FILE)