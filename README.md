# Ek-Chuah MCP -- MCP-AEC (lector C3)

Servidor MCP **read-only** que sirve el **graph_aec** (Archivo Epistemico) en la nube:
cualquier IA lee la via epistemica de forma autonoma, y por **I3** cada lectura trae
su porque. Hermano del substrato [`Ek-Chuah`](https://github.com/Entheos69/Ek-Chuah)
(misma topologia que `concept-sediment` / `concept-sediment-mcp`: substrato y servidor
MCP son repos separados).

> Contrato de origen: `concept-sediment/docs/ek_chuah/` -- CONVERGENCIA (proceso 2),
> LECTOR_C3 (esta spec), SCHEMA_YAML_AEC, y REPORTE_CodeCS_a_CodeMCP_paso4_habilitado.

## Arquitectura (camino B -- Guardian 2026-06-27)

La nube **no** recibe la proyeccion ya construida; recibe el **log** (forma Q) y
**reconstruye** la proyeccion aqui. Honra forma Q / I1, evita el desync de proyeccion
one-way, y reusa el stack `concept-sediment-mcp`.

```
  Scripts/AEC/log/inscripciones.jsonl   (durable local, la VERDAD -- CodeCS)
        |  exportador del log  (SOL JOINT a CodeCS; bytes nivel-1 NO cruzan)
        v
  aec_log (JSONB append-only)           copia replicada del log en la nube
        |  projection_build.rebuild_projection  (idempotente, det.)
        v
  7 tablas graph_aec + afirmacion.embedding   proyeccion REGENERABLE
        |  queries.py (read-only)
        v
  4 tools MCP  ->  cualquier IA
```

## Tools (4 core, todas read-only)

| Tool | Job | Entrada |
|---|---|---|
| `aec_search` | "?ya investigue X?" -- indice anti-re-investigacion (embeddings + ILIKE) | `query` |
| `aec_get_via` | una afirmacion + su via ascendente completa (I3) | `af_id` |
| `aec_resolve` | un referente -> cadena de versiones (I4) | `url` \| `referente_id` \| `content_hash` |
| `aec_get_necesidad` | traza descendente: que trajo una indagacion y que sobrevivio | `nec_id` |

`aec_search` devuelve cada hit con **stub** de via (nunca dato pelon); `aec_get_via`
expande la via completa. 5a tool `aec_divergencia` **diferida** (LECTOR_C3 §8).

## Membrana (el candado que no se rompe)

- **No escribe.** Read-only por construccion + `get_readonly_session` (SET TRANSACTION
  READ ONLY) + rol de BD solo-lectura en Railway. Aportar va por Estratega, fuera de aqui.
- **No baja URLs.** Sin web; la `url` es metadato forense que devuelve, no que fetcha.
- **No sirve nivel 1.** Devuelve `content_hash`, nunca los bytes del snapshot.

## Estructura

```
server.py            FastMCP + Starlette + 4 tools aec_*
queries.py           lectura read-only (ports de proyeccion.py)
projection_build.py  rebuild de aec_log -> 7 tablas + embeddings (camino B)
schema.sql           DDL: aec_log + 7 tablas proyeccion + pgvector
db.py                engine; get_readonly_session (defensa membrana)
normaliza_url.py     espejo vendorizado de D-ver-1 (canonical URL)
```

## Local

```bash
cp .env.example .env          # DATABASE_URL (Postgres+pgvector) + OPENAI_API_KEY
python projection_build.py --replicate ../AEC/log/inscripciones.jsonl  # carga aec_log
python projection_build.py --rebuild                                   # reconstruye + embeddings
python server.py                                                       # lector en :8000
```

Falsador I1 (rebuild = identico, excluye embedding):
`python projection_build.py --dump` debe coincidir con
`Ek-Chuah/proyeccion.dump_logico` sobre el mismo log.

## Deploy (gateado por Guardian)

El deploy del MCP-AEC **invalida sesiones MCP** (CONVERGENCIA §9). Antes: YAMLs de
cierre `reviewed` + MTV + baselines si cambian tools. Railway apunta a **este** repo,
no al substrato. Post-deploy: reiniciar cliente -> reconectar MCP.

## Pendiente JOINT

El **exportador del log** local -> `aec_log` es jurisdiccion CodeCS (SOL del borde,
`docs/ek_chuah/SOL_EXPORTADOR_LOG_AEC_2026-06-27.md`). Mientras tanto,
`projection_build.py --replicate` lo simula desde el archivo local para pruebas.
