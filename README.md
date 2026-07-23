# LOTERIA ANGUILA — LA QUE NUNCA FALLA ANGUILA

Banca web (Flask) solo para **La Anguila** (sorteos 8:00 AM – 10:00 PM).

## Local

```bash
pip install -r requirements.txt
# No uses DATABASE_URL=null — déjala vacía para SQLite (banca.db)
python -c "from app import app; app.run(host='127.0.0.1', port=5000)"
```

Login por defecto (cámbialo en producción):

- `jose0219` / `Moose555@` (super_admin)
- o crea usuarios desde el panel admin

## Render (manual)

1. Conecta este repo en Render
2. Crea una base **PostgreSQL**
3. Variables:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | Internal Database URL de Postgres (no `null`) |
| `SECRET_KEY` | cadena aleatoria larga |
| `CLOSE_BEFORE_DRAW_MINUTES` | `5` (opcional) |

4. Start: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120 --workers 1 --worker-class gthread --threads 4`

## Notas

- Ticket térmico: **LA QUE NUNCA FALLA ANGUILA**, `NO PAGAMOS SIN TICKET`, `REVISA SU TICKET`, `BUENA SUERTE`
- Catálogo de venta: solo **La Anguila**
