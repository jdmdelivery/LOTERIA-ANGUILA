# JDM Anguila

Sistema de venta de Quiniela/Palé Anguila (República Dominicana), listo para **GitHub + Render**.

## Qué incluye

- Venta de tickets (Quiniela / Palé) con snapshot de pagos
- Colector `ConectateAnguillaResultCollector` (API pública Conectate `/sessions`)
- Confirmación por doble lectura → detección de ganadores
- Pantalla **Premios → Validar ticket** y pago con confirmación `PAGAR PREMIO`
- Recibos térmicos 58/80 mm (HTML + ESC/POS)
- Reimpresión auditada
- Pruebas obligatorias en `tests/test_obligatorios.py`
- Auditoría de fuente en `docs/`

## Usuarios por defecto (cámbialos en Render)

| Usuario | Clave | Rol |
| --- | --- | --- |
| `admin` | `admin123` | administrador |
| `jose` | `jose123` | cajero |

## Local

```bash
cd "loteria anguila"
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python -m unittest tests.test_obligatorios -v
python app.py
```

Abre http://127.0.0.1:5000

## Subir a GitHub

```bash
cd "loteria anguila"
git init
git add .
git commit -m "JDM Anguila listo para venta y deploy en Render"
gh repo create jdm-anguila --private --source=. --remote=origin --push
```

(O crea el repo en github.com y haz `git remote add origin ...` + `git push -u origin main`.)

## Deploy en Render

1. En [render.com](https://render.com) → **New** → **Blueprint**
2. Conecta el repo de GitHub
3. Usa el `render.yaml` del proyecto (crea web + Postgres)
4. Define secretos:
   - `ADMIN_PASSWORD`
   - `CAJERO_PASSWORD`
   - `SECRET_KEY` (auto si Blueprint)
5. Deploy → abre la URL → login cajero → **Venta**

### Variables útiles

- `BANK_NAME`, `BANK_ADDRESS`, `BANK_PHONE`, `TICKET_MESSAGE`
- `CLOSE_BEFORE_DRAW_MINUTES` (default 5)
- `PAY_QUINIELA_PRIMERA=70`, `PAY_QUINIELA_SEGUNDA=8`, `PAY_QUINIELA_TERCERA=4`, `PAY_PALE=1200`
- `DATABASE_URL` (Render Postgres)

## Operación diaria

1. **Venta**: elegir sorteo abierto, cargar quinielas/palés, vender (imprime ticket)
2. Tras el sorteo el colector corre cada 60s; confirma con 2 lecturas idénticas
3. **Premios**: buscar ticket → si `GANADOR PENDIENTE` confirmar `PAGAR PREMIO`
4. **Admin → Resultados**: entrada manual para `ANGUILA_1200` (12 PM, fuente no disponible) o fallos

## Notas importantes

- `ANGUILA_1200` (12:00 PM): **FUENTE_NO_DISPONIBLE** → solo manual, sin auto-pago
- Slugs engañosos en Conectate: 1 PM = `anguila-12-pm`, 6 PM = `anguila-5-pm`
- La Cuarteta está excluida
- CANDIDATO nunca paga; solo CONFIRMADO
- El dinero de caja solo baja al confirmar pago físico

## Banca La Que Nunca Falla

No se modificó el proyecto original. Los recibos térmicos se reimplementaron en este repo adaptados a **JDM ANGUILA**.
