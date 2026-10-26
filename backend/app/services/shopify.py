import httpx

from app.config import (
    SHOPIFY_SHOP,
    SHOPIFY_API_VERSION,
    SHOPIFY_CLIENT_ID,
    SHOPIFY_CLIENT_SECRET,
)


async def obtener_access_token():
    url = f"https://{SHOPIFY_SHOP}.myshopify.com/admin/oauth/access_token"

    data = {
        "grant_type": "client_credentials",
        "client_id": SHOPIFY_CLIENT_ID,
        "client_secret": SHOPIFY_CLIENT_SECRET,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            data=data
        )

    response.raise_for_status()

    return response.json()["access_token"]


async def ejecutar_graphql(query, variables=None):
    token = await obtener_access_token()

    url = (
        f"https://{SHOPIFY_SHOP}.myshopify.com"
        f"/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    )

    headers = {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "variables": variables or {},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload
        )

    response.raise_for_status()

    return response.json()


async def obtener_metricas_productos(product_ids=None):
    consultas = {
        "sold7": "FROM sales SHOW net_items_sold GROUP BY product_id SINCE -7d",
        "sold30": "FROM sales SHOW net_items_sold GROUP BY product_id SINCE -30d",
        "sellThrough": "FROM inventory SHOW sell_through_rate GROUP BY product_id SINCE -30d",
        "descuento": "FROM sales SHOW gross_sales, discounts GROUP BY product_id SINCE -30d",
    }

    metricas = {}

    if product_ids:
        product_ids = set(str(product_id) for product_id in product_ids)

    for nombre, shopifyql in consultas.items():
        query = """
        query($query: String!) {
          shopifyqlQuery(query: $query) {
            tableData {
              columns {
                name
                dataType
                displayName
              }
              rows
            }
            parseErrors
          }
        }
        """

        data = await ejecutar_graphql(
            query,
            {"query": shopifyql}
        )

        resultado = data["data"]["shopifyqlQuery"]

        if resultado["parseErrors"]:
            raise Exception(
                f"Error ShopifyQL en {nombre}: "
                f"{resultado['parseErrors']}"
            )

        for row in resultado["tableData"]["rows"]:
            product_id = row.get("product_id")

            if not product_id:
                continue

            if product_ids and str(product_id) not in product_ids:
                continue

            if product_id not in metricas:
                metricas[product_id] = {}

            if nombre == "sold7":
                metricas[product_id]["sold7"] = (
                    int(row["net_items_sold"])
                    if row.get("net_items_sold") is not None
                    else None
                )

            elif nombre == "sold30":
                metricas[product_id]["sold30"] = (
                    int(row["net_items_sold"])
                    if row.get("net_items_sold") is not None
                    else None
                )

            elif nombre == "sellThrough":
                metricas[product_id]["sellThrough"] = (
                    float(row["sell_through_rate"]) * 100
                    if row.get("sell_through_rate") is not None
                    else None
                )

            elif nombre == "descuento":
                gross_sales = row.get("gross_sales")
                discounts = row.get("discounts")

                if gross_sales is None or discounts is None:
                    metricas[product_id]["descuento"] = None
                else:
                    gross_sales = float(gross_sales)
                    discounts = abs(float(discounts))

                    if gross_sales == 0:
                        metricas[product_id]["descuento"] = None
                    else:
                        metricas[product_id]["descuento"] = {
                            "pct": (discounts / gross_sales) * 100,
                            "ventaBruta": gross_sales,
                            "descuento": discounts,
                        }

    return metricas
