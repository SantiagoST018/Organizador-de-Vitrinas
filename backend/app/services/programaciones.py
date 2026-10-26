import json
import sqlite3
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DB_DIR = BASE_DIR / "app" / "data"
DB_PATH = DB_DIR / "programaciones.db"


def conectar() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)

    conexion = sqlite3.connect(DB_PATH)
    conexion.row_factory = sqlite3.Row
    return conexion


def inicializar_db() -> None:
    with conectar() as conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS programaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                handle TEXT NOT NULL,
                cadencia TEXT NOT NULL DEFAULT 'diaria',
                dias TEXT NOT NULL DEFAULT '[1,2,3,4,5]',
                hora TEXT NOT NULL DEFAULT '06:00',
                accion TEXT NOT NULL DEFAULT 'borrador',
                criterios TEXT NOT NULL,
                respetar INTEGER NOT NULL DEFAULT 0,
                activa INTEGER NOT NULL DEFAULT 1,
                ultima TEXT,
                creada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actualizada_en TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def serializar_programacion(fila: sqlite3.Row) -> dict[str, Any]:
    dato = dict(fila)
    dato["dias"] = json.loads(dato["dias"])
    dato["criterios"] = json.loads(dato["criterios"])
    dato["activa"] = bool(dato["activa"])
    dato["ultima"] = json.loads(dato["ultima"]) if dato["ultima"] else None
    return dato


def listar_programaciones() -> list[dict[str, Any]]:
    with conectar() as conexion:
        filas = conexion.execute("""
            SELECT *
            FROM programaciones
            ORDER BY id DESC
        """).fetchall()

    return [serializar_programacion(fila) for fila in filas]


def obtener_programacion(programacion_id: int) -> dict[str, Any] | None:
    with conectar() as conexion:
        fila = conexion.execute(
            "SELECT * FROM programaciones WHERE id = ?",
            (programacion_id,),
        ).fetchone()

    return serializar_programacion(fila) if fila else None


def crear_programacion(datos: dict[str, Any]) -> dict[str, Any]:
    with conectar() as conexion:
        cursor = conexion.execute("""
            INSERT INTO programaciones (
                nombre, handle, cadencia, dias, hora, accion,
                criterios, respetar, activa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos["nombre"],
            datos["handle"],
            datos.get("cadencia", "diaria"),
            json.dumps(datos.get("dias", [1, 2, 3, 4, 5])),
            datos.get("hora", "06:00"),
            datos.get("accion", "borrador"),
            json.dumps(datos["criterios"]),
            datos.get("respetar", 0),
            int(datos.get("activa", True)),
        ))

        programacion_id = cursor.lastrowid

    resultado = obtener_programacion(programacion_id)
    if resultado is None:
        raise RuntimeError("No se pudo recuperar la programación creada")

    return resultado


def actualizar_programacion(
    programacion_id: int,
    datos: dict[str, Any],
) -> dict[str, Any] | None:
    campos = {
        "nombre": datos.get("nombre"),
        "handle": datos.get("handle"),
        "cadencia": datos.get("cadencia"),
        "dias": datos.get("dias"),
        "hora": datos.get("hora"),
        "accion": datos.get("accion"),
        "criterios": (
            datos.get("criterios")
        ),
        "respetar": datos.get("respetar"),
        "activa": int(datos["activa"]) if "activa" in datos else None,
    }

    with conectar() as conexion:
        existente = conexion.execute(
            "SELECT id FROM programaciones WHERE id = ?",
            (programacion_id,),
        ).fetchone()

        if not existente:
            return None

        actual = obtener_programacion(programacion_id)

        valores = {}
        for campo, valor in campos.items():
            if valor is None:
                valores[campo] = actual[campo]
            else:
                valores[campo] = valor

        # SQLite no admite listas directamente: guardarlas como JSON.
        valores["dias"] = json.dumps(valores["dias"])
        valores["criterios"] = json.dumps(valores["criterios"])

        conexion.execute("""
            UPDATE programaciones
            SET nombre = ?, handle = ?, cadencia = ?, dias = ?,
                hora = ?, accion = ?, criterios = ?, respetar = ?,
                activa = ?, actualizada_en = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            valores["nombre"],
            valores["handle"],
            valores["cadencia"],
            valores["dias"],
            valores["hora"],
            valores["accion"],
            valores["criterios"],
            valores["respetar"],
            valores["activa"],
            programacion_id,
        ))

    return obtener_programacion(programacion_id)


def eliminar_programacion(programacion_id: int) -> bool:
    with conectar() as conexion:
        cursor = conexion.execute(
            "DELETE FROM programaciones WHERE id = ?",
            (programacion_id,),
        )

    return cursor.rowcount > 0


def actualizar_estado(
    programacion_id: int,
    activa: bool,
) -> dict[str, Any] | None:
    return actualizar_programacion(
        programacion_id,
        {"activa": activa},
    )


def registrar_ejecucion(
    programacion_id: int,
    resultado: dict[str, Any],
) -> dict[str, Any] | None:
    with conectar() as conexion:
        cursor = conexion.execute("""
            UPDATE programaciones
            SET ultima = ?, actualizada_en = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            json.dumps(resultado, ensure_ascii=False),
            programacion_id,
        ))

    if cursor.rowcount == 0:
        return None

    return obtener_programacion(programacion_id)


inicializar_db()
