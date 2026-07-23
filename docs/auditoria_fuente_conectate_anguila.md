# Auditoría — Fuente Conectate Anguila

**Estado:** investigación completa — **detenerse y esperar aprobación**  
**Proyecto:** JDM Anguila (`loteria anguila`)  
**Fecha:** 2026-07-23  
**Alcance cumplido:** solo investigación de fuente. Sin scraper productivo, sin pago de premios, sin cambios a Banca La Que Nunca Falla.

---

## 1. Entregables de esta fase

| # | Entregable | Ubicación |
| --- | --- | --- |
| 1 | Lista verificada de las 15 páginas/horarios | este informe + `docs/fuente_resultados_conectate_anguila.md` |
| 2 | Método real de extracción | API JSON `GET /sessions` |
| 3 | Ejemplos HTML/JSON/endpoint | `research/conectate_raw/` y prueba local |
| 4 | Prueba de extracción local | `docs/extraction_proof_conectate_anguila.json` |
| 5 | Identificación de La Cuarteta | sección 5 |
| 6 | Informe de riesgos | sección 6 |
| 7 | Confirmación Banca intacta | sección 7 |

---

## 2. Cómo carga Conectate los resultados (evidencia)

### 2.1 HTML

- Sitio Nuxt en `loterias.conectate.com.do`.
- Cada sorteo tiene ruta `/anguilla/<seo_url>/`.
- El HTML incluye preload:

```html
<link rel="preload" as="fetch" crossorigin="anonymous"
  href="/anguilla/anguila-8-am/_payload.json?...">
```

- Config pública en página:

```js
apiBase: "https://api.conectate.com.do/conectate"
wsEndpoint: "wss://client-ws.kiskooloterias.com"
```

- Los números del sorteo **no** se obtienen de forma fiable parseando el HTML visual.

### 2.2 Network / XHR / Fetch

Endpoint público real (no inventado), usado por el frontend:

```http
GET https://api.conectate.com.do/conectate/sessions?date=2026-07-23T14:00:00.000Z
```

Respuesta: JSON array con `game_id`, `sessions`, `lastSession`.

Fragmento real (Anguila 8:00 AM):

```json
{
  "game_id": "6a5114d907d516b9c5101dd5",
  "lastSession": {
    "date": "2026-07-23T04:00:00.000Z",
    "score": [["97", "96", "14"]],
    "updatedAt": "..."
  }
}
```

### 2.3 Scripts JavaScript

En el bundle Nuxt (`entry.js`) se observó:

- `$fetch.create({ baseURL: public.apiBase })`
- `fetchSiteForDate` → `$api("sessions", { query: { date, limit } })`
- Modelo de UI: `session.score[0]` renderizado por `score.vue` / `session.vue`

### 2.4 Preferencia técnica

**Preferir la respuesta JSON del endpoint `/sessions`** sobre scraping visual.  
Usar `_payload.json` solo como apoyo para descubrir `game_id` y `seo_url`.

---

## 3. Lista verificada de los 15 horarios

| Código | Horario | URL verificada | Estado |
| --- | --- | --- | --- |
| ANGUILA_0800 | 8:00 AM | `/anguilla/anguila-8-am/` | VERIFICADO |
| ANGUILA_0900 | 9:00 AM | `/anguilla/anguila-9-am/` | VERIFICADO |
| ANGUILA_1000 | 10:00 AM | `/anguilla/anguila-10-am/` | VERIFICADO |
| ANGUILA_1100 | 11:00 AM | `/anguilla/anguila-11-am/` | VERIFICADO |
| ANGUILA_1200 | 12:00 PM | — | **FUENTE_NO_DISPONIBLE** |
| ANGUILA_1300 | 1:00 PM | `/anguilla/anguila-12-pm/` (slug engañoso) | VERIFICADO_CON_RIESGO |
| ANGUILA_1400 | 2:00 PM | `/anguilla/anguila-2-pm/` | VERIFICADO |
| ANGUILA_1500 | 3:00 PM | `/anguilla/anguila-3-pm/` | VERIFICADO |
| ANGUILA_1600 | 4:00 PM | `/anguilla/anguila-4pm/` | VERIFICADO |
| ANGUILA_1700 | 5:00 PM | `/anguilla/anguila-5pm/` | VERIFICADO |
| ANGUILA_1800 | 6:00 PM | `/anguilla/anguila-5-pm/` (slug engañoso) | VERIFICADO_CON_RIESGO |
| ANGUILA_1900 | 7:00 PM | `/anguilla/anguila-7pm/` | VERIFICADO |
| ANGUILA_2000 | 8:00 PM | `/anguilla/anguila-8pm/` | VERIFICADO |
| ANGUILA_2100 | 9:00 PM | `/anguilla/anguila-9-pm/` | VERIFICADO |
| ANGUILA_2200 | 10:00 PM | `/anguilla/anguila-10pm/` | VERIFICADO |

### Hallazgos críticos de URL

1. **No asumir el patrón `anguila-N-am/pm`.**  
   Varios slugs omiten el guion (`anguila-4pm`, `anguila-7pm`, `anguila-10pm`).

2. **`/anguilla/anguila-12-pm/`**  
   En el HTML real, `<title>` y `<h1>` corresponden a **Anguila 1 PM**, no a 12 PM.

3. **`/anguilla/anguila-5-pm/`**  
   Corresponde a **Anguila 6 PM**.  
   **`/anguilla/anguila-5pm/`** corresponde a **Anguila 5 PM**.

4. **Anguila 12:00 PM**  
   Tiene `game_id` en CMS/API, pero **no** página propia verificable.  
   Marcar `FUENTE_NO_DISPONIBLE`, notificar administrador, permitir entrada manual, **no** auto-detectar/pagar.

Sitemap oficial de Anguilla (18 URLs): 14 quinielas Anguila + 4 Cuarteta. No hay slug dedicado correcto para 12:00 PM.

---

## 4. Prueba de extracción guardada localmente

Ejecutada el 2026-07-23 con User-Agent identificable:

`JDM-Anguila-Auditor/1.0 (+research; ConectateAnguilla investigation)`

Archivos:

- `docs/extraction_proof_conectate_anguila.json`
- `research/analysis/extraction_proof.json`
- `research/conectate_raw/api/sessions_latest.json`
- `research/conectate_raw/api/sessions_latest.sha256`
- Script reproducible: `research/extract_anguilla_results.py`

Ejemplos capturados (muestra):

| Código | Resultado | Fecha API |
| --- | --- | --- |
| ANGUILA_0800 | 97-96-14 | 2026-07-23 |
| ANGUILA_0900 | 70-37-11 | 2026-07-23 |
| ANGUILA_1000 | 65-67-69 | 2026-07-23 |
| ANGUILA_1400 | 85-32-**09** | 2026-07-22 |
| ANGUILA_1500 | 84-**00**-85 | 2026-07-22 |
| ANGUILA_1900 | **06**-89-**06** | 2026-07-22 |

Evidencia de aislamiento por horario: a ~10:03 AST del 23/07, solo 8/9/10 AM tenían `date` del 23; el resto seguía en 22 — consistente con sorteos aún no ocurridos.

---

## 5. La Cuarteta (exclusión)

Páginas bajo Anguilla, **excluidas**:

| Nombre | URL |
| --- | --- |
| La Cuarteta 10:00 AM | `/anguilla/la-cuarteta-manana/` |
| La Cuarteta 1:00 PM | `/anguilla/cuarteta-medio-dia/` |
| La Cuarteta 6:00 PM | `/anguilla/cuarteta-tarde/` |
| La Cuarteta 9:00 PM | `/anguilla/cuarteta-noche/` |

Diferenciadores observados:

- Nombre contiene “Cuarteta”
- `game_id` distinto
- `score` de **4** posiciones (no 3)
- Ejemplo: `21-09-96-07`
- Puede publicarse incompleto (`["05","75","59",""]`) — reforzar doble lectura y rechazo

También excluir del alcance: pronósticos, números calientes/fríos, años anteriores, otras loterías del mismo API bulk.

---

## 6. Informe de riesgos

| Riesgo | Severidad | Mitigación propuesta |
| --- | --- | --- |
| Slug ≠ horario (12-pm = 1 PM; 5-pm = 6 PM) | Alta | Mapear por `game_id` + validar title/H1; tests de regresión de URL |
| 12:00 PM sin página verificable | Alta | `FUENTE_NO_DISPONIBLE` + manual + sin auto-pago |
| Colisión CMS: dos `siteGames` con mismo `seo_url` | Alta | No resolver por slug solo; usar `game_id` canónico |
| API `/sessions` devuelve **todas** las loterías | Media | Filtrar allowlist de `game_id` Anguila |
| `date` sin hora de sorteo | Media | Reloj oficial local + mapa de horarios; no inferir hora desde `date` |
| Resultado incompleto / en construcción | Alta | Doble lectura idéntica; rechazar celdas vacías |
| Dependencia de tercero (Conectate/Kiskoo) | Alta | Timeout, reintentos, backoff, salud, revisión a 45 min |
| Cambio de `game_id` o slugs sin aviso | Media | Config editable `ANGUILLA_RESULT_SOURCES` + alerta admin |
| reCAPTCHA presente en config del sitio | Baja/Media | No evadir; si bloquea API pública, degradar a manual |
| Confundir Cuarteta con Anguila | Alta | Allowlist + exigir exactamente 3 números |
| Usar estadísticas/hot/cold | Alta | Fuera de alcance; no implementar |
| Pago automático prematuro | Crítica (fase futura) | Esta fase **no** conecta colector a pagos |

**No observado en esta investigación:** necesidad de login, cookies de sesión, ni tokens privados para leer `/sessions`.

---

## 7. Confirmación: Banca La Que Nunca Falla no fue modificada

- El workspace `loteria anguila` estaba vacío al inicio (sin código de banca).
- Solo se crearon artefactos de investigación/documentación **dentro** de `loteria anguila`.
- No se abrió, copió ni alteró código de “Banca La Que Nunca Falla” en esta fase.
- La reutilización de recibos térmicos queda **fuera** de esta fase y requerirá autorización explícita en una fase posterior.

---

## 8. Qué NO se hizo (a propósito)

- No se implementó `ConectateAnguillaResultCollector` productivo.
- No se conectó ningún resultado a detección de ganadores ni a caja.
- No se creó pantalla de premios.
- No se modificó ni copió aún el diseño de tickets de otra banca.
- No se inventaron endpoints.

---

## 9. Recomendación para la siguiente fase (pendiente de tu aprobación)

1. Formalizar `ANGUILLA_RESULT_SOURCES` en configuración editable con los `game_id` auditados.
2. Implementar colector separado usando **solo** `GET /sessions` + allowlist.
3. Tratar `ANGUILA_1200` como manual hasta existir página/fuente verificable.
4. Exigir confirmación humana antes de habilitar auto-pago en `VERIFICADO_CON_RIESGO` (1 PM y 6 PM).
5. Recién después, cablear detección de ganadores sobre resultados `CONFIRMADO`.

---

## 10. Decisión solicitada

**Detenido aquí.**  
¿Apruebas continuar con la implementación del colector (sin pago automático aún) usando este mapa y el endpoint `/sessions`?
