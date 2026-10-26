from fastapi import APIRouter, HTTPException, Query

from app.config import SHOPIFY_SHOP, SHOPIFY_API_VERSION
from app.services.shopify import (
    obtener_access_token,
    ejecutar_graphql,
    obtener_metricas_productos,
)


router = APIRouter(
    prefix="/api",
    tags=["Organizador de Vitrinas"]
)


@router.get("/health")
def health():
    return {
        "status": "ok"
    }


@router.get("/config")
def config():
    return {
        "shop": SHOPIFY_SHOP,
        "api_version": SHOPIFY_API_VERSION
    }


@router.get("/sitios")
def sitios():
    return [
        {
            "clave": "pe",
            "nombre": "Perú",
            "pais": "Perú",
            "marca": "American Eagle",
            "dominio": "ae.com.pe",
            "moneda": "PEN",
            "activo": True,
            "fuente": "config",
            "faltaDominio": False
        }
    ]


@router.get("/info")
async def info():
    query = """
    {
      shop {
        name
        currencyCode
      }
      productsCount {
        count
      }
      collectionsCount {
        count
      }
    }
    """

    data = await ejecutar_graphql(query)

    return {
        "tienda": data["data"]["shop"]["name"],
        "extraido": True,
        "productos_en_tienda": data["data"]["productsCount"]["count"],
        "colecciones_en_tienda": data["data"]["collectionsCount"]["count"],
        "nota": None
    }


@router.get("/productos")
async def productos():
    query = """
    query($after: String) {
      products(first: 250, after: $after) {
        nodes {
          id
          title
          handle
          status
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    productos = []
    after = None

    while True:
        variables = {
            "after": after
        }

        data = await ejecutar_graphql(query, variables)
        resultado = data["data"]["products"]

        for producto in resultado["nodes"]:
            productos.append({
                "id": producto["id"].split("/")[-1],
                "name": producto["title"],
                "handle": producto["handle"],
                "status": producto["status"]
            })

        page_info = resultado["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        after = page_info["endCursor"]

    return productos




@router.get("/resumen-metricas")
async def resumen_metricas():
    query = """
    query($after: String) {
      products(first: 250, after: $after) {
        nodes {
          id
          featuredImage {
            url
          }
          variants(first: 250) {
            nodes {
              inventoryQuantity
              selectedOptions {
                name
                value
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    productos = []
    after = None

    try:
        while True:
            data = await ejecutar_graphql(query, {"after": after})
            resultado = data["data"]["products"]

            for producto in resultado["nodes"]:
                stock = 0
                tallas = []

                for variante in producto["variants"]["nodes"]:
                    cantidad = variante.get("inventoryQuantity")
                    if cantidad is not None:
                        stock += cantidad

                    opciones = variante.get("selectedOptions", [])
                    talla = next(
                        (
                            opcion["value"]
                            for opcion in opciones
                            if opcion["name"].lower() in ("size", "talla")
                        ),
                        None
                    )

                    tallas.append({
                        "talla": talla,
                        "stock": cantidad
                    })

                productos.append({
                    "id": producto["id"].split("/")[-1],
                    "stock": stock,
                    "sizes": tallas,
                    "image": (
                        producto["featuredImage"]["url"]
                        if producto.get("featuredImage")
                        else None
                    )
                })

            page_info = resultado["pageInfo"]
            if not page_info["hasNextPage"]:
                break

            after = page_info["endCursor"]

        ids = [producto["id"] for producto in productos]
        metricas = await obtener_metricas_productos(ids)

        for producto in productos:
            producto.update(metricas.get(producto["id"], {}))

        return {
            "productos": productos,
            "total": len(productos)
        }

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo calcular el resumen general: {exc}"
        ) from exc


@router.get("/colecciones")
async def colecciones():
    query = """
    query($after: String) {
      collections(first: 250, after: $after) {
        nodes {
          id
          title
          handle
          sortOrder
          productsCount {
            count
          }
          ruleSet {
            appliedDisjunctively
            rules {
              column
              relation
              condition
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
    """

    colecciones = []
    after = None

    while True:
        variables = {
            "after": after
        }

        data = await ejecutar_graphql(query, variables)

        resultado = data["data"]["collections"]

        for coleccion in resultado["nodes"]:
            colecciones.append({
                "handle": coleccion["handle"],
                "titulo": coleccion["title"],
                "gid": coleccion["id"],
                "sortOrder": coleccion["sortOrder"],
                "reglas": (
                    coleccion["ruleSet"]["rules"]
                    if coleccion["ruleSet"]
                    else []
                ),
                "totalEnShopify": (
                    coleccion["productsCount"]["count"]
                    if coleccion["productsCount"]
                    else 0
                ),
                "cargados": 0,
                "gestionada": True
            })

        page_info = resultado["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        after = page_info["endCursor"]

    return colecciones


@router.get("/vitrina")
async def vitrina(handle: str = Query(...)):
    query = """
    query($handle: String!, $after: String) {
      collectionByHandle(handle: $handle) {
        id
        title
        handle
        sortOrder
        products(first: 250, after: $after) {
          nodes {
            id
            title
            handle
            status
            productType
            onlineStoreUrl
            featuredImage {
              url
            }
            variants(first: 250) {
              nodes {
                sku
                barcode
                price
                inventoryQuantity
                selectedOptions {
                  name
                  value
                }
              }
            }
          }
          pageInfo {
            hasNextPage
            endCursor
          }
        }
      }
    }
    """

    productos = []
    after = None
    coleccion = None
    metricas = {}

    while True:
        variables = {
            "handle": handle,
            "after": after
        }

        data = await ejecutar_graphql(query, variables)

        print("GRAPHQL VITRINA:", data)

        coleccion = data["data"]["collectionByHandle"]

        if coleccion is None:
            return {
                "coleccion": None,
                "productos": {},
                "metricas": {},
                "vitrina": {
                    "publicado": [],
                    "borrador": [],
                    "version": 0,
                    "estado": "SIN_COLECCION",
                    "historial": [],
                    "anterior": None
                }
            }

        resultado_productos = coleccion["products"]

        productos.extend(resultado_productos["nodes"])

        page_info = resultado_productos["pageInfo"]

        if not page_info["hasNextPage"]:
            break

        after = page_info["endCursor"]

    productos_data = {}
    items = []

    for posicion, producto in enumerate(productos, start=1):
        producto_id = producto["id"].split("/")[-1]

        variantes = producto.get("variants", {}).get("nodes", [])

        precio = None
        stock = 0
        sizes = []

        for variante in variantes:
            if precio is None and variante.get("price") is not None:
                precio = float(variante["price"])

            cantidad = variante.get("inventoryQuantity")

            if cantidad is not None:
                stock += cantidad

            opciones = variante.get("selectedOptions", [])

            talla = next(
                (
                    op["value"]
                    for op in opciones
                    if op["name"].lower() in ("size", "talla")
                ),
                None
            )

            sizes.append({
                "talla": talla,
                "stock": cantidad
            })

        productos_data[producto_id] = {
            "id": producto_id,
            "ref": variantes[0].get("sku") if variantes else None,
            "name": producto["title"],
            "handle": producto["handle"],
            "status": producto["status"],
            "price": precio,
            "stock": stock,
            "sizes": sizes,
            "sizesTotal": len(sizes),
            "sizesWith": sum(
                1
                for s in sizes
                if s["stock"] is not None and s["stock"] > 0
            ),
            "productType": producto.get("productType"),
            "url": producto.get("onlineStoreUrl"),
            "image": (
                producto.get("featuredImage", {}).get("url")
                if producto.get("featuredImage")
                else None
            )
        }

        items.append({
            "id": producto_id,
            "pos": posicion
        })

    # Obtener métricas únicamente de los productos
    # que pertenecen a esta colección
    product_ids = [item["id"] for item in items]

    metricas = {}

    return {
        "coleccion": {
            "handle": coleccion["handle"],
            "titulo": coleccion["title"],
            "gid": coleccion["id"],
            "sortOrder": coleccion["sortOrder"],
            "items": items
        },
        "productos": productos_data,
        "metricas": metricas,
        "vitrina": {
            "publicado": [item["id"] for item in items],
            "borrador": items,
            "version": 1,
            "estado": "PUBLICADO",
            "historial": [],
            "anterior": None
        }
    }

@router.get("/metricas")
async def metricas(ids: str = Query(default="")):
    try:
        product_ids = [
            product_id.strip()
            for product_id in ids.split(",")
            if product_id.strip()
        ]

        if not product_ids:
            return {}

        return await obtener_metricas_productos(product_ids)

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc)
        ) from exc

@router.get("/shopify/test")
async def shopify_test():
    token = await obtener_access_token()

    return {
        "shop": SHOPIFY_SHOP,
        "autenticacion": "ok",
        "token_recibido": bool(token)
    }


@router.get("/shopify/graphql-test")
async def shopify_graphql_test():
    query = """
    {
      products(first: 5) {
        nodes {
          id
          title
          handle
          status
        }
      }
    }
    """

    return await ejecutar_graphql(query)

# ---------------- PROGRAMACIONES ----------------

from datetime import time
from pydantic import BaseModel, Field, field_validator
from app.services.programaciones import (
    listar_programaciones,
    obtener_programacion,
    crear_programacion,
)


class ProgramacionCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    handle: str = Field(min_length=1, max_length=255)
    cadencia: str = "diaria"
    dias: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    hora: str = "06:00"
    accion: str = "borrador"
    criterios: list[dict] = Field(min_length=1)
    respetar: int = Field(default=0, ge=0)
    activa: bool = True

    @field_validator("nombre", "handle")
    @classmethod
    def validar_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("Este campo no puede estar vacío")
        return valor

    @field_validator("cadencia")
    @classmethod
    def validar_cadencia(cls, valor: str) -> str:
        if valor not in {"diaria", "dias"}:
            raise ValueError("La cadencia debe ser diaria o dias")
        return valor

    @field_validator("dias")
    @classmethod
    def validar_dias(cls, valor: list[int]) -> list[int]:
        if any(dia < 0 or dia > 6 for dia in valor):
            raise ValueError("Los días deben estar entre 0 y 6")
        if len(valor) != len(set(valor)):
            raise ValueError("No se permiten días repetidos")
        return valor

    @field_validator("hora")
    @classmethod
    def validar_hora(cls, valor: str) -> str:
        try:
            time.fromisoformat(valor)
        except ValueError as exc:
            raise ValueError("La hora debe tener formato HH:MM") from exc
        if len(valor) != 5:
            raise ValueError("La hora debe tener formato HH:MM")
        return valor

    @field_validator("accion")
    @classmethod
    def validar_accion(cls, valor: str) -> str:
        if valor not in {"borrador", "publicar"}:
            raise ValueError("La acción debe ser borrador o publicar")
        return valor


@router.get("/programaciones")
def api_listar_programaciones():
    return listar_programaciones()


@router.get("/programaciones/{programacion_id}")
def api_obtener_programacion(programacion_id: int):
    programacion = obtener_programacion(programacion_id)
    if programacion is None:
        raise HTTPException(
            status_code=404,
            detail="Programación no encontrada",
        )
    return programacion


@router.post("/programaciones", status_code=201)
def api_crear_programacion(datos: ProgramacionCrear):
    return crear_programacion(datos.model_dump())


@router.patch("/programaciones/{programacion_id}")
def api_actualizar_programacion(
    programacion_id: int,
    datos: dict,
):
    from app.services.programaciones import actualizar_programacion

    resultado = actualizar_programacion(programacion_id, datos)
    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Programación no encontrada",
        )
    return resultado


@router.patch("/programaciones/{programacion_id}/estado")
def api_actualizar_estado_programacion(
    programacion_id: int,
    datos: dict,
):
    from app.services.programaciones import actualizar_estado

    if "activa" not in datos or not isinstance(datos["activa"], bool):
        raise HTTPException(
            status_code=422,
            detail="Envía el campo activa como true o false",
        )

    resultado = actualizar_estado(programacion_id, datos["activa"])
    if resultado is None:
        raise HTTPException(
            status_code=404,
            detail="Programación no encontrada",
        )
    return resultado


@router.delete("/programaciones/{programacion_id}", status_code=204)
def api_eliminar_programacion(programacion_id: int):
    from app.services.programaciones import eliminar_programacion

    if not eliminar_programacion(programacion_id):
        raise HTTPException(
            status_code=404,
            detail="Programación no encontrada",
        )
    return None
