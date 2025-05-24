from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator
import httpx
import stripe

stripe.api_key = "sk_test_51RRjTyH5EWZhGwlWOI5bzYEmdPSdEQkz86w01pL9omFI0Tz74jgkZj9BBX92cErzsooa4hOBNwF5s4ZENlqaTOwk00wEztErIq"

app = FastAPI(title="Mi API - Artículos FERREMAS")

BASE_URL = "https://ea2p2assets-production.up.railway.app/data/articulos"
HEADERS = {"x-authentication": "SaGrP9ojGS39hU9ljqbXxQ=="}

# Modelo para el pago
class PagoRequest(BaseModel):
    nombre: str
    precio: int

# Obtener todos los artículos
@app.get("/articulos")
async def obtener_articulos():
    async with httpx.AsyncClient() as client:
        r = await client.get(BASE_URL, headers=HEADERS)
        return r.json()

# Buscar artículo por ID
@app.get("/articulos/{id}")
async def obtener_articulo_por_id(id: str):
    async with httpx.AsyncClient() as client:
        r = await client.get(BASE_URL, headers=HEADERS)
        data = r.json()
        for articulo in data:
            if articulo["id"].lower() == id.lower():
                return articulo
        raise HTTPException(status_code=404, detail="Artículo no encontrado")

# Buscar por nombre, marca o categoría
@app.get("/articulos/buscar")
async def buscar_articulo(
    nombre: str = Query(None),
    marca: str = Query(None),
    categoria: str = Query(None)
):
    async with httpx.AsyncClient() as client:
        r = await client.get(BASE_URL, headers=HEADERS)
        data = r.json()
        resultados = []

        for articulo in data:
            if (
                (not nombre or nombre.lower() in articulo["nombre"].lower()) and
                (not marca or marca.lower() in articulo["marca"].lower()) and
                (not categoria or categoria.lower() in articulo["categoria"].lower())
            ):
                resultados.append(articulo)

        if not resultados:
            raise HTTPException(status_code=404, detail="No se encontraron coincidencias")
        return resultados

# Crear sesión de pago con Stripe
@app.post("/pagar")
async def crear_pago(pago: PagoRequest):
    nombre = pago.nombre
    precio = pago.precio

    if precio <= 0:
        raise HTTPException(status_code=400, detail="El precio debe ser un número positivo")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'clp',
                    'product_data': {
                        'name': nombre,
                    },
                    'unit_amount': precio * 100,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://tuweb.com/exito',
            cancel_url='https://tuweb.com/cancelado',
        )
        return {"checkout_url": session.url}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Obtener vendedor por código
@app.get("/vendedores/{codigo}")
async def contactar_vendedor(codigo: str):
    if not codigo.startswith("V") or len(codigo) != 4:
        raise HTTPException(status_code=400, detail="Código inválido")
    
    url_vendedores = "https://ea2p2assets-production.up.railway.app/data/vendedores"
    headers = {"x-authentication": "SaGrP9ojGS39hU9ljqbXxQ=="}

    async with httpx.AsyncClient() as client:
        r = await client.get(url_vendedores, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener datos de vendedores externos")
        data = r.json()

        for vendedor in data:
            if vendedor["id"].upper() == codigo.upper():
                return vendedor
        
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")

# Modelo para enviar mensaje al vendedor
class MensajeVendedorRequest(BaseModel):
    codigo: str
    mensaje: str

    @validator("codigo")
    def validar_codigo(cls, v):
        if not v.startswith("V") or not v[1:].isdigit():
            raise ValueError("El código debe comenzar con 'V' seguido de números")
        numero = int(v[1:])
        if numero < 1 or numero > 21:
            raise ValueError("El código debe estar entre V001 y V021")
        return v

    @validator("mensaje")
    def validar_mensaje(cls, v):
        if len(v) < 500:
            raise ValueError("El mensaje debe tener al menos 500 caracteres")
        return v

# Enviar mensaje al vendedor
@app.post("/contactar_vendedor")
async def enviar_mensaje_vendedor(request: MensajeVendedorRequest):
    url_vendedores = "https://ea2p2assets-production.up.railway.app/data/vendedores"
    headers = {"x-authentication": "SaGrP9ojGS39hU9ljqbXxQ=="}

    async with httpx.AsyncClient() as client:
        r = await client.get(url_vendedores, headers=headers)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener datos de vendedores externos")
        data = r.json()

        vendedor = next((v for v in data if v["id"].upper() == request.codigo.upper()), None)
        if not vendedor:
            raise HTTPException(status_code=404, detail="Vendedor no encontrado")

        return {
            "detalle": f"Mensaje enviado al vendedor {vendedor['nombre']} ({vendedor['email']})",
            "mensaje": request.mensaje[:50] + "..."
        }

# Convertir CLP a USD usando API pública sin API key
@app.get("/convertir-clp-a-usd")
async def convertir_clp_a_usd(monto: float = Query(1.0, gt=0, description="Monto en CLP a convertir")):
    url = "https://open.er-api.com/v6/latest/CLP"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="No se pudo obtener la tasa de cambio")

        data = response.json()

        # Verificamos que exista la tasa para USD
        if "rates" not in data or "USD" not in data["rates"]:
            raise HTTPException(status_code=500, detail="No se encontró la tasa de cambio USD")

        tasa_usd = data["rates"]["USD"]
        equivalente_usd = round(monto * tasa_usd, 2)

        return {
            "tasa_usd": tasa_usd,
            "monto_clp": monto,
            "equivalente_usd": equivalente_usd
        }
