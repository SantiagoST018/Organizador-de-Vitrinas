from fastapi import FastAPI

app = FastAPI(
    title="Organizador de Vitrinas PE",
    version="1.0.0"
)


@app.get("/")
def inicio():
    return {
        "mensaje": "Backend Organizador de Vitrinas PE funcionando"
    }
