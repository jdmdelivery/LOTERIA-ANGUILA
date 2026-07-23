# Fuente de resultados — Conectate Anguila

**Fase:** solo investigación  
**Fecha de auditoría:** 2026-07-23  
**Dominio permitido:** `https://loterias.conectate.com.do/anguilla/`  
**API pública observada:** `https://api.conectate.com.do/conectate`  
**Prueba local:** `docs/extraction_proof_conectate_anguila.json` y `research/analysis/extraction_proof.json`

No se guardaron cookies, sesiones, credenciales ni tokens privados.

---

## Método real de extracción (preferido)

Conectate es una app **Nuxt**. Los números **no** vienen embebidos de forma usable en el HTML visible de la página del sorteo.

Flujo real observado:

1. La página `/anguilla/<seo_url>/` precarga metadata vía `/anguilla/<seo_url>/_payload.json`.
2. El frontend configura `apiBase = https://api.conectate.com.do/conectate`.
3. Los resultados se cargan con:

```http
GET https://api.conectate.com.do/conectate/sessions?date=<ISO-8601 datetime>
User-Agent: JDM-Anguila-Auditor/1.0 (+research; ConectateAnguilla investigation)
Accept: application/json
```

4. La respuesta es un arreglo JSON. Cada elemento tiene:
   - `game_id`
   - `sessions[]`
   - `lastSession`

5. Estructura del resultado de Anguila (quiniela de 3 posiciones):

```json
{
  "game_id": "6a5114d907d516b9c5101dd5",
  "lastSession": {
    "_id": "...",
    "game_id": "6a5114d907d516b9c5101dd5",
    "date": "2026-07-23T04:00:00.000Z",
    "score": [["97", "96", "14"]],
    "updatedAt": "2026-07-23T12:01:xx.xxxZ"
  }
}
```

### Campos

| Campo | Ubicación JSON |
| --- | --- |
| Fecha del día del sorteo | `lastSession.date` |
| Primera | `lastSession.score[0][0]` |
| Segunda | `lastSession.score[0][1]` |
| Tercera | `lastSession.score[0][2]` |
| Identidad del horario | `game_id` (mapeado a `ANGUILLA_RESULT_SOURCES`) |

### Notas de validación

- Conservar ceros iniciales: la API ya entrega strings `"00"`, `"01"`, `"09"`.
- `session.date` es la **fecha del día** en zona `America/Santo_Domingo` (medianoche AST = `T04:00:00.000Z`), **no** la hora del sorteo.
- La hora se valida por el mapeo `code ↔ game_id ↔ URL/título`, nunca inventando endpoints.
- Rechazar scores incompletos (celdas vacías) y scores con ≠ 3 números para Anguila.
- Excluir La Cuarteta: 4 posiciones y `game_id` distintos.

### Métodos descartados / secundarios

| Método | Resultado |
| --- | --- |
| Scraping visual del HTML | Los números no aparecen de forma estable en el HTML SSR útil |
| `_payload.json` | Sirve para metadata/`game_id`/SEO; **no** trae `score` de la sesión |
| Endpoints inventados (`/games/{id}`, etc.) | 404 — no usar |
| `feed/game-stats` | Existe, pero es estadísticas; no es la fuente de resultado del día |
| WebSocket `wss://client-ws.kiskooloterias.com` | Declarado en config Nuxt; **no** se usó ni se requiere para lectura batch |

---

## Configuración propuesta: `ANGUILLA_RESULT_SOURCES`

Editable. Cada horario es independiente.

| Código | Nombre recibido | URL verificada | `seo_url` | `game_id` | Estado |
| --- | --- | --- | --- | --- | --- |
| `ANGUILA_0800` | Anguila 8:00 AM | https://loterias.conectate.com.do/anguilla/anguila-8-am/ | `anguila-8-am` | `6a5114d907d516b9c5101dd5` | VERIFICADO |
| `ANGUILA_0900` | Anguila 9:00 AM | https://loterias.conectate.com.do/anguilla/anguila-9-am/ | `anguila-9-am` | `6a3e91bd5036a431f5f3e801` | VERIFICADO |
| `ANGUILA_1000` | Anguila 10:00 AM | https://loterias.conectate.com.do/anguilla/anguila-10-am/ | `anguila-10-am` | `6966a6d3ea7015c3b8a3d635` | VERIFICADO |
| `ANGUILA_1100` | Anguila 11:00 AM | https://loterias.conectate.com.do/anguilla/anguila-11-am/ | `anguila-11-am` | `6a3e935d5036a431f5f3e8b2` | VERIFICADO |
| `ANGUILA_1200` | Anguila 12:00 PM | — | — | `6a3e94f85036a431f5f407b0` | **FUENTE_NO_DISPONIBLE** |
| `ANGUILA_1300` | Anguila 1:00 PM | https://loterias.conectate.com.do/anguilla/anguila-12-pm/ | `anguila-12-pm` | `6966a6d3ea7015c3b8a3d611` | VERIFICADO_CON_RIESGO |
| `ANGUILA_1400` | Anguila 2:00 PM | https://loterias.conectate.com.do/anguilla/anguila-2-pm/ | `anguila-2-pm` | `6a3e96e25036a431f5f40c87` | VERIFICADO |
| `ANGUILA_1500` | Anguila 3:00 PM | https://loterias.conectate.com.do/anguilla/anguila-3-pm/ | `anguila-3-pm` | `6a3e97a25036a431f5f41eef` | VERIFICADO |
| `ANGUILA_1600` | Anguila 4:00 PM | https://loterias.conectate.com.do/anguilla/anguila-4pm/ | `anguila-4pm` | `6a5116a607d516b9c5102db7` | VERIFICADO |
| `ANGUILA_1700` | Anguila 5:00 PM | https://loterias.conectate.com.do/anguilla/anguila-5pm/ | `anguila-5pm` | `6a5116f607d516b9c510302f` | VERIFICADO |
| `ANGUILA_1800` | Anguila 6:00 PM | https://loterias.conectate.com.do/anguilla/anguila-5-pm/ | `anguila-5-pm` | `6966a6d3ea7015c3b8a3d617` | VERIFICADO_CON_RIESGO |
| `ANGUILA_1900` | Anguila 7:00 PM | https://loterias.conectate.com.do/anguilla/anguila-7pm/ | `anguila-7pm` | `6a51185b07d516b9c5104c69` | VERIFICADO |
| `ANGUILA_2000` | Anguila 8:00 PM | https://loterias.conectate.com.do/anguilla/anguila-8pm/ | `anguila-8pm` | `6a511ab407d516b9c510788d` | VERIFICADO |
| `ANGUILA_2100` | Anguila 9:00 PM | https://loterias.conectate.com.do/anguilla/anguila-9-pm/ | `anguila-9-pm` | `6966a6d3ea7015c3b8a3d61d` | VERIFICADO |
| `ANGUILA_2200` | Anguila 10:00 PM | https://loterias.conectate.com.do/anguilla/anguila-10pm/ | `anguila-10pm` | `6a511b0a07d516b9c5107d05` | VERIFICADO |

### Alertas de administrador (obligatorias)

1. **`ANGUILA_1200` — FUENTE_NO_DISPONIBLE**  
   No hay página propia verificable. El slug `anguila-12-pm` **no** corresponde a las 12:00 PM en el HTML real.  
   Acción: entrada manual; no detectar ni pagar ganadores automáticamente.

2. **`ANGUILA_1300` — slug engañoso**  
   La página de 1:00 PM vive en `/anguilla/anguila-12-pm/` (title/H1 = Anguila 1 PM).

3. **`ANGUILA_1800` — slug engañoso**  
   La página de 6:00 PM vive en `/anguilla/anguila-5-pm/` (title/H1 = Anguila 6 PM).  
   Distinto de `/anguilla/anguila-5pm/` (5:00 PM).

---

## Detalle por sorteo

### ANGUILA_0800

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-8-am/
- **Código:** `ANGUILA_0800`
- **Nombre recibido:** Anguila 8:00 AM
- **Método:** JSON API `GET /sessions?date=...` filtrado por `game_id`
- **Endpoint:** `https://api.conectate.com.do/conectate/sessions?date=<ISO>`
- **Fecha:** `lastSession.date`
- **Primera / Segunda / Tercera:** `score[0][0..2]`
- **Ejemplo real (2026-07-23):** `97 - 96 - 14`
- **Evidencia de horario:** `game_id=6a5114d907d516b9c5101dd5` + página `anguila-8-am` + title de 8:00 AM; resultado del día 23 (ya sorteado a la hora de la prueba)

### ANGUILA_0900

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-9-am/
- **Código:** `ANGUILA_0900`
- **Nombre:** Anguila 9:00 AM
- **Método / endpoint / campos:** iguales al patrón anterior
- **Ejemplo real (2026-07-23):** `70 - 37 - 11`
- **Evidencia:** `game_id=6a3e91bd5036a431f5f3e801` + slug `anguila-9-am`

### ANGUILA_1000

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-10-am/
- **Código:** `ANGUILA_1000`
- **Ejemplo real (2026-07-23):** `65 - 67 - 69`
- **Evidencia:** `game_id=6966a6d3ea7015c3b8a3d635`

### ANGUILA_1100

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-11-am/
- **Código:** `ANGUILA_1100`
- **Ejemplo real al momento de la prueba:** `86 - 72 - 83` con `date=2026-07-22...`  
  (aún no actualizado al 23 a la hora de la captura ~10:03 AST) → evidencia de aislamiento por horario/`game_id`

### ANGUILA_1200

- **URL:** no verificable
- **Código:** `ANGUILA_1200`
- **Estado:** `FUENTE_NO_DISPONIBLE`
- **game_id CMS/API (solo referencia, no usar para pago automático):** `6a3e94f85036a431f5f407b0`
- **Ejemplo API (no confirmable vía página propia):** `69 - 71 - 31` (`date=2026-07-22`)
- **Acción:** manual + notificación admin

### ANGUILA_1300

- **URL real:** https://loterias.conectate.com.do/anguilla/anguila-12-pm/
- **Código:** `ANGUILA_1300`
- **Nombre en HTML:** Anguila 1 PM
- **Método:** API + `game_id=6966a6d3ea7015c3b8a3d611`
- **Ejemplo:** `67 - 01 - 89` (cero inicial conservado en `01`)
- **Evidencia:** title/H1 de la URL `anguila-12-pm` dicen **1 PM**, no 12 PM

### ANGUILA_1400

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-2-pm/
- **Ejemplo:** `85 - 32 - 09` (cero en `09`)

### ANGUILA_1500

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-3-pm/
- **Ejemplo:** `84 - 00 - 85` (cero en `00`)

### ANGUILA_1600

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-4pm/  
  (sin guion antes de `pm`)
- **Ejemplo:** `47 - 47 - 48`

### ANGUILA_1700

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-5pm/
- **Ejemplo:** `38 - 98 - 49`

### ANGUILA_1800

- **URL real:** https://loterias.conectate.com.do/anguilla/anguila-5-pm/
- **Nombre HTML:** Anguila 6 PM
- **Ejemplo:** `63 - 94 - 95`
- **Riesgo:** no confundir con `anguila-5pm` (5 PM)

### ANGUILA_1900

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-7pm/
- **Ejemplo:** `06 - 89 - 06` (ceros en `06`)

### ANGUILA_2000

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-8pm/
- **Ejemplo:** `15 - 08 - 13`

### ANGUILA_2100

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-9-pm/
- **Ejemplo:** `77 - 51 - 27`

### ANGUILA_2200

- **URL:** https://loterias.conectate.com.do/anguilla/anguila-10pm/
- **Ejemplo:** `60 - 08 - 46`

---

## La Cuarteta (excluir expresamente)

Aunque viven bajo `/anguilla/`, **no** son fuente de Quiniela/Palé Anguila.

| Código | Nombre | URL | `game_id` | Señal de rechazo |
| --- | --- | --- | --- | --- |
| `CUARTETA_1000` | La Cuarteta 10:00 AM | `/anguilla/la-cuarteta-manana/` | `6966a6d3ea7015c3b8a3d63b` | 4 posiciones (puede llegar incompleta) |
| `CUARTETA_1300` | La Cuarteta 1:00 PM | `/anguilla/cuarteta-medio-dia/` | `6966a6d3ea7015c3b8a3d623` | 4 números, ej. `21-09-96-07` |
| `CUARTETA_1800` | La Cuarteta 6:00 PM | `/anguilla/cuarteta-tarde/` | `6966a6d3ea7015c3b8a3d629` | 4 números, ej. `17-07-40-66` |
| `CUARTETA_2100` | La Cuarteta 9:00 PM | `/anguilla/cuarteta-noche/` | `6966a6d3ea7015c3b8a3d62f` | 4 números, ej. `65-18-42-48` |

Regla: si `score[0].length !== 3` o el `game_id` está en la lista Cuarteta → **RECHAZADO**.

---

## Ejemplo mínimo de extracción local

Script de investigación (no conectado a pagos):

`research/extract_anguilla_results.py`

Salida:

- `research/analysis/extraction_proof.json`
- `docs/extraction_proof_conectate_anguila.json`
- hash SHA-256 de la respuesta API en `research/conectate_raw/api/sessions_latest.sha256`

---

## Alcance de esta fase

- ✔ Lista verificada de páginas / estados
- ✔ Método real (API JSON pública)
- ✔ Ejemplos reales guardados localmente
- ✔ Identificación separada de La Cuarteta
- ✖ Colector productivo **no** implementado
- ✖ No conectado a detección/pago de premios
