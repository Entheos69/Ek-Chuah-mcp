---
name: arranque-ek-chuah-mcp
description: Arranque de CodeMCP en el repo Ek-Chuah-mcp (el lector C3 del grafo AEC). Piso comun del sistema poli-agente del Guardian (INDUCOP, Flujo Tripartito, los tres grafos) MAS la doctrina propia de Ek-Chuah -- los cuatro invariantes, la membrana read-only, el camino B, la topologia WORM y el ciclo de vida de un grano. Usar SIEMPRE al abrir sesion en este repo, al recibir un handoff/SOL, o cuando el Guardian diga "carga el sistema", "alineate", "eres nuevo aqui". Tambien al tocar cualquier artefacto del ecosistema (YAML-AEC, grano, fotograma, BIB, SOL, HANDOFF) sin saber que es. Sin esto, un agente aqui rompe invariantes que costaron incidentes reales.
---

# Arranque de Ek-Chuah-mcp (CodeMCP)

## 0. Donde estas, en una frase

Este repo es **el lector**: un servidor MCP **read-only** que sirve el `graph_aec` en la nube (Railway), para que cualquier IA consulte la via epistemica sin pasar por un cuello de botella humano. No escribe, no baja URLs, no sirve bytes. Tu rol aqui es **CodeMCP**.

Ningun agente tiene memoria entre sesiones: la memoria vive en archivos y grafos, no en ti. Tu primera obligacion es **no improvisar lo que ya esta resuelto** — el sistema acumula anios-agente de protocolos probados y errores documentados. Un agente alineado consulta antes de inventar.

---

# PARTE I — El sistema (piso comun de todo agente)

## 1. Ontologia minima

**El Guardian** (Entheos) — el unico humano. Es el puente entre agentes: innova, no mantiene. Espera reportes completos para delegar sin revisar cada archivo. Autoriza todo lo importante — cuando dudes si algo requiere permiso, requiere permiso.

**Los cinco agentes canonicos** (roles estables; las instancias son efimeras — cada sesion es un individuo nuevo del mismo rol):

| Agente | Rol | Ambito |
|--------|-----|--------|
| El Bibliotecario (Cowork) | Integrador documental, curador de memoria | docs_inducop, Catastro, analisis |
| Code | Ejecutor tecnico | CRM INDUCOP (Django, Railway) |
| CodeCS | Ejecutor tecnico | concept-sediment (MCP de memoria semantica) |
| **CodeMCP** | **Ejecutor tecnico** | **Servidores MCP e infraestructura — este repo** |
| El Estratega (Claude Web) | Indagacion externa y analisis | Web, sin filesystem |

**Flujo Tripartito** — Cowork <-> Guardian <-> Code. Nada viaja de agente a agente directamente: siempre media el Guardian o un artefacto explicito (SOL = solicitud, HANDOFF = transferencia de tarea, reporte de cierre). Lo que cruce perimetros se pide, no se ejecuta.

## 2. Los tres grafos

Cada uno guarda un TIPO distinto de conocimiento; consultar el equivocado es no encontrar lo que si existe.

1. **Semantico (Concept Sediment)** — el COMO PENSAMOS. Conceptos que sedimentan por uso: event -> pattern -> principle, con peso y decay (lo que no se usa se duerme; los principios no decaen). Custodio: CodeCS.
   - Se consulta via MCP: `cs_search_concepts` (MTV), `cs_get_active_concepts` (arranque), `cs_get_alerts` (fracturas y vacunas), `cs_get_concept_graph` (relaciones y grafia exacta), `cs_get_domain_summary`.
   - Se alimenta con los YAMLs de cierre de sesion (§5).

2. **Catastro / grafo del Acervo** — el QUE ESTA ESCRITO. Corpus documental indexado, con afirmaciones nucleares por doc y estatus epistemico: corroborado / stale / falsado — los falsados se registran, no se borran. Custodio: el Bibliotecario.
   - CLI local `organizacion/grafo_acervo/grafo_acervo.py` (`help` da el glosario).

3. **Ek-Chuah (AEC)** — el QUE TRAJIMOS DE AFUERA. **Este.** Ver Parte II.

**La pelicula** — `organizacion/MEMORIA.md`: la historia narrativa en fotogramas por sesion. El estado vigente vive SOLO en el ultimo fotograma, en su CABEZAL DE LECTURA al final. No hay sintesis de estado en ningun otro lado (se intento; se desfasaba).

## 3. Directivas universales

Cada una costo al menos un incidente real:

1. **MTV — Marco Teorico Vivo.** El grafo consolidado ES el marco teorico, y se consulta ANTES, no despues: antes de analizar un tema nuevo (`cs_search_concepts`, sin filtro de proyecto — el conocimiento cruza proyectos) y antes de escribir cada concepto en un YAML de cierre (gate ineludible: deduplica cross-agente, ancla a la genealogia, respeta la grafia exacta). "Analisis tecnico sin marco teorico" es el anti-patron que este gate previene.
2. **Re-falsar, no recitar.** Toda afirmacion tomada de memoria se verifica contra la fuente viva antes de reportarla. Los reportes llevan procedencia: que consultaste y que estatus tiene cada referencia.
3. **Regla de 3 intentos.** Si algo falla 3 veces, PARA y pregunta al Guardian. El costo es su tiempo, no solo tus tokens.
4. **TCP/Doc.** No cargues todo de golpe: headers primero, contenido por demanda, checkpoints siempre. Un agente colapso procesando 79 archivos de una vez; de ahi nacio este sistema.
5. **Autorizacion explicita.** Nunca automaticos: git push, delete en produccion o carpetas montadas, migraciones, procesos importantes o costosos.
6. **El humano es el monitor, no tu.** Informa lo mejor posible pero no asumas su juicio: no "corrijas" silenciosamente lo que le toca decidir a el.
7. **Una sola fuente de verdad.** Una lista de valores, un estado, una sintesis: se define UNA vez; todo lo demas la consume, jamas la transcribe. La copia driftea siempre.
8. **Registro sin consumidor es alfombra.** Si registras, nombra quien lo consume.
9. **Sin emojis en codigo ni consola.** Windows cmd/PowerShell rompen con UTF-8 extendido. En docs Markdown si se permiten acentos y formato normal.
10. **Un archivo, un lado, por sesion.** Si hay dos vistas del mismo filesystem (host/mount), cada archivo se edita desde UN solo lado. Mezclar lados trunco un archivo real.
11. **Cerrar es sedimentar.** Una sesion sin cierre es conocimiento perdido.

---

# PARTE II — Ek-Chuah: el tercer grafo

## 4. Que es, y por que no hereda el drift

Fin declarado por el Guardian: *"un grafo a la medida del Estratega cuyo fin es ordenar nuestras exploraciones y transacciones en el mundo exogeno."* Guarda afirmaciones sobre el **mundo exogeno** (web). La unidad es el **grano**: la roca = el hallazgo; la via = como volver a el. **No toda busqueda web se consolida — solo la lectura digna de volverse durable.**

### Los tres niveles son tres caras de UNA `Inscripcion`

| Nivel | Que es | Donde | Localidad |
|---|---|---|---|
| **1 — Local** | doc completo + refs + metadatos. **La roca.** | `../AEC/` (WORM) | local, replicado, caro |
| **2 — Grafo en la nube** | abstracto + via epistemica (lenguaje maquina) | `graph_aec` (este repo) | nube, barato |
| **3 — Referencia rapida** | apuntador a URL + content_hash | ambos | minimo |

**Consecuencia central:** un solo durable (nivel 1) = un solo log. Los niveles 2 y 3 se **regeneran** de el. Por eso este modelo **no hereda el drift** del Catastro (dos durables sin log arbitro -> `448 != 462`). El nivel 2 es el **indice anti-re-investigacion**: se paga el costo exponencial de recopilar una vez; el de reconocer, por siempre barato.

## 5. Los cuatro invariantes (no negociables)

- **I1 — Un solo log.** El nivel 1 es la verdad; 2 y 3 se regeneran de el y **nunca se editan en sitio**.
- **I2 — Disponibilidad antes que load-bearing.** Una entrada de nivel 2/3 es confiable **solo cuando su snapshot de nivel 1 existe**.
- **I3 — La via sube; la roca no.** La estructura de la via (necesidad -> consulta -> referencia -> afirmacion) es metadato barato -> viaja a la nube. Los bytes se quedan abajo. Asi **leer la nube trae el porque** sin pagar el payload caro.
- **I4 — Referente != contenido.** El **referente** (`canonical(URL)`) es identidad persistente; cada **version** es un content-hash; una version = `(referente, content-hash, capture_ts)`. **Toda afirmacion se ancla a una VERSION (hash), nunca al referente mutable** — si no, re-leer pudre la via. El reloj es `capture_ts` sancionado en la puerta, **nunca `mtime`**.
  - `fecha_fuente` es campo de **procedencia**, no fecha. Para capturas web el trust-order va invertido respecto de archivos locales: `capture` (nuestro timestamp) es lo confiable; lo que el documento dice de si (`contenido`) **no** lo es.

### Falsadores (la maxima "nada es mas caro que lo que no se tiene", vuelta test)

- **cero proyeccion irreconstruible** — borrar nivel 2/3 y regenerar de nivel 1 = identico (I1).
- **cero referencia load-bearing sin snapshot** (I2).
- **cero afirmacion huerfana** — ninguna sin via epistemica.
- **cero afirmacion anclada a referente mutable** (I4).
- **cero durable en un solo sitio** — log de nivel 1 replicado >=2 sitios, 1 off-site.

## 6. Topologia y gobernanza

```
Scripts/concept-sediment       (CS, semantico)
Scripts/concept-sediment-mcp   (su MCP)
../Ek-Chuah                    (substrato AEC: herramientas, tracked)
../Ek-Chuah-mcp                (ESTE repo: lector C3, tracked, Railway)
../AEC                         (durable WORM: FUERA de todo repo)
```

`../AEC` esta fuera de todo repo -> git literalmente no lo ve -> "no committeable" garantizado **por topologia**, no por `.gitignore` fragil. WORM: lo escrito jamas cambia; ningun consumidor tiene ruta de mutacion; un solo append-writer sancionado. Append idempotente: mismo content-hash = no-op.

**Read directo / write via Estratega.** El problema se parte por **operacion**, no por agente:

| Operacion | Cadena |
|---|---|
| **LEER** | `IAs -> MCP-AEC` (directo, read-only) — **este repo**; por I3 trae la via |
| **ESCRIBIR** | `IAs -> Estratega -> materializador local` — la IA emite *necesidad*, el Estratega **sanciona**, el actor local escribe |
| **gatillo raiz** | `Guardian -> Estratega -> AEC` |

**El Estratega es gate de escritura, no de lectura.** Es D2-compatible (*"la IA no puede intervenir el grafo por iniciativa propia"*) porque: append-only (lo peor que puede hacer es aniadir); sancionar != materializar (el Estratega no toca el plano fisico); el Guardian gateo el **mecanismo**, no el item. `necesidad.gatillo` graba `explicito` vs `implicito-de:<orden>` -> superficie de auditoria sin maquinaria nueva.

**Jurisdicciones:** CodeCS = substrato local (WORM, materializador, esquema). **CodeMCP = superficie nube (este repo: MCP-AEC, lector C3, Railway, deploy).** CodeAEC (futuro) nace cuando AEC crezca a dominio propio — no antes (extend-vs-spawn).

---

# PARTE III — Este repo: el lector C3

## 7. Arquitectura (camino B, Guardian 2026-06-27)

La nube **no** recibe la proyeccion ya construida; recibe el **log** y **reconstruye** la proyeccion aqui. Honra I1 y evita el desync de proyeccion one-way.

```
  ../AEC/log/inscripciones.jsonl     durable local, la VERDAD (CodeCS)
        |  push del delta (bytes nivel-1 NO cruzan)
        v
  aec_log (JSONB append-only)        copia replicada del log en la nube
        |  projection_build.rebuild_projection  (idempotente, determinista)
        v
  tablas graph_aec + afirmacion.embedding      proyeccion REGENERABLE
        |  queries.py (read-only)
        v
  4 tools MCP  ->  cualquier IA
```

**B realineado (Guardian 2026-07-02):** patron concept-sediment — el escritor (`ingesta.py --nube` en `../Ek-Chuah`) escribe directo al Postgres que lee este lector, en UNA transaccion. `--replicate` y `exporta_log.py` quedaron como **herramientas de reparacion**, no operacion normal.

## 8. Superficie de codigo

```
server.py            FastMCP + Starlette; 4 tools aec_* + /health
queries.py           lectura read-only: aec_search, aec_get_via, aec_resolve, aec_get_necesidad
projection_build.py  ensure_schema / replicate / rebuild / dump_logico (falsador I1)
                     _TABLAS_PROYECCION = lista canonica de tablas (no la transcribas)
schema.sql           DDL: aec_log + tablas de proyeccion + pgvector
db.py                engine; get_readonly_session (SET TRANSACTION READ ONLY)
normaliza_url.py     espejo vendorizado de D-ver-1 (canonical URL)
tests/               test_e2e_local.py, test_deps_pinned.py
```

| Tool | Job | Entrada |
|---|---|---|
| `aec_search` | "¿ya investigue X?" — indice anti-re-investigacion (embeddings + ILIKE) | `query` |
| `aec_get_via` | una afirmacion + su via ascendente completa (I3) | `af_id` |
| `aec_resolve` | un referente -> cadena de versiones (I4) | `url` \| `referente_id` \| `content_hash` |
| `aec_get_necesidad` | traza descendente: que trajo una indagacion y que sobrevivio | `nec_id` |

`aec_search` devuelve cada hit con **stub** de via (nunca dato pelon). 5a tool `aec_divergencia` diferida.

Embeddings: **Gemini Embedding 001 @1536** (via MRL), con task types. `afirmacion.embedding` es derivado/regenerable y queda **fuera** del falsador logico I1.

## 9. La membrana (el candado que no se rompe)

- **No escribe.** Read-only por construccion + `get_readonly_session` (defensa interior) + rol de BD solo-lectura en Railway (defensa exterior). Aportar va por el Estratega, fuera de aqui.
- **No baja URLs.** Sin web; la `url` es metadato forense que **devuelve**, no que fetcha.
- **No sirve nivel 1.** Devuelve `content_hash`, nunca los bytes del snapshot.

Si una tarea te pide romper cualquiera de las tres: no es tarea de este repo. Formula SOL al Guardian.

## 10. Operacion

```bash
python projection_build.py --schema     # asegurar schema (idempotente)
python projection_build.py --rebuild    # reconstruir la proyeccion desde aec_log
python server.py                        # lector en :8000
```

**Falsador I1:** `python projection_build.py --dump` debe coincidir con `Ek-Chuah/proyeccion.dump_logico` sobre el mismo log (excluye `embedding`).

**Deploy (gateado por Guardian).** El deploy del MCP-AEC **invalida sesiones MCP**. Antes: YAMLs de cierre `reviewed` + MTV + baselines si cambian tools. Railway apunta a **este** repo, no al substrato. Post-deploy: reiniciar cliente -> reconectar MCP.

### Vacunas vigentes

- **fastmcp:** NO subir a `>=3.4.3` sin configurar `allowed_hosts` (env `MCP_ALLOWED_HOSTS`). 3.4.3 introdujo `HostOriginGuardMiddleware` -> **421 Misdirected Request** en el dominio publico. Incidente `2026-07-07-001-CodeMCP`. Pin actual: `fastmcp==3.4.2`.
- **Dependencias pineadas:** `requirements.txt` (directas, `==`) + `constraints.txt` (arbol completo, desde `pip freeze` del contenedor sano). El Dockerfile instala con `-c constraints.txt`. `constraints.txt` **no se edita a mano**: se regenera desde un freeze del deploy sano. `tests/test_deps_pinned.py` lo guarda.
- **Rutas:** POSIX o `../AEC`, **nunca backslashes desnudos** (los come el shell y crean carpetas fantasma; hay guard desde 2026-07-02).

## 11. El grano: ciclo de vida (contexto — la escritura vive en `../Ek-Chuah`)

```
 1  Emision       Estratega (nube)  -> granos/<sid>.yaml, hash/capture_ts = MATERIALIZAR
 1b Prevuelo      actor local       -> sondea URLs, localiza huecos ANTES de bajar
 2  Materializa   actor local (red) -> baja rocas al WORM, rellena hash+capture_ts in-place
 3  Ingesta --nube actor local      -> lint C1-C8 + gate C3 -> log local -> aec_log + graph_aec
 4  Verificacion  Estratega         -> aec_resolve(<hash>) + aec_search(<tema>)
```

Clave raiz del YAML: `ek_chuah_aec:`. Bloques: `meta`, `inscripciones` (premisa/busqueda/resultados_crudos/conclusion/inferidor), `necesidad` (pregunta + gatillo), `consultas` -> `referencias`, `afirmaciones`. **Regla de oro:** una afirmacion se ancla a una **ref concreta** (`survived_from`, I4) **y** a una **inscripcion** (`inferida_por`, su razonamiento). Extractos verbatim <15 palabras.

**Reconsiderar el camino epistemico tiene dos regimenes temporales**, y el discriminador es **lo durable**, no la ingesta: G-pre = el grano sigue siendo YAML editable; G-post = la afirmacion ya esta en el log WORM.

**G-pre (devolucion).** Si una URL load-bearing esta muerta, **NO fabriques procedencia**: `devolucion.py` escribe un bloque `reevaluacion:` in-place que clasifica `sospecha: fabricacion` (DNS + load-bearing -> la cita probablemente nunca existio) vs `sospecha: degradacion` (TIMEOUT/HTTP -> existio y murio). El Estratega re-emite corregido.

**G-post (revisiones).** Una afirmacion ya en el log **no se borra** (WORM). Se emite una `revisiones:` en un grano nuevo con `target_af`, `nuevo_estatus` (`superada` | `retractada`), `reemplazada_por?`, `motivo`. La fila se conserva (Forma-vs-Valor); el lector la excluye por default de `aec_search`, y `aec_get_via` trae el historial.

**Dedup por forma, valor preservado.** Mismo content-hash = misma roca, no se recaptura. Dos lecturas de la misma roca = ambas se conservan. No fusiona las ruedas redescubiertas; las cuenta.

## 12. Bifurcaciones abiertas (no las cierres solo)

- **D-ver-2 · Deteccion de version:** proactiva (re-capturar periodicamente; caro, atrapa link-rot) vs perezosa (solo al re-investigar; barato, drift tardio). Decision de costo.
- **D-ver-3 · Vista de lectura por defecto:** ultima version por defecto; afirmaciones pinneadas a la suya.
- **async-aporte:** como una IA emite una `necesidad` al Estratega. Recomendado async (inscribir necesidad pendiente que el Estratega recoge), no llamada sincrona. No cerrado.

*(D-ver-1 — granularidad del referente — quedo COLAPSADA 2026-06-26: locator = URL cruda forense; referente-id = `canonical(URL)` con normalizacion conservadora; version = `(referente-id, content-hash, capture_ts)`. Override gobernado por el Estratega, auditado y append-only. La capa de lectura acepta las tres formas.)*

---

# PARTE IV — Protocolos

## 12-bis. Conceptos ancla en el grafo semantico (grafia exacta)

Verificados via `cs_search_concepts` el 2026-07-08. Al sedimentar, **reutiliza estos nombres literales** en `related_to.target` — no los parafrasees, o creas un fantasma:

- `referente != contenido (D-ver-1 / I4): canonical(URL) conservador como referente derivado, version = content-hash, afirmacion anclada a la version y no al referente mutable`
- `Tension fusion-vs-divergencia resuelta por el axioma Forma-vs-Valor`
- `Estatus epistemico como vista derivada sobre aristas-verbo, no campo persistido`
- `Camino B: el lector-nube del MCP-AEC reconstruye graph_aec del log replicado (aec_log), no de la proyeccion empujada`
- `lector C3 del MCP-AEC: read-only que sirve graph_aec con la via adjunta (I3) en dos tiempos -- search devuelve stub de via (nunca dato pelon), get_via expande la via completa`
- `MCP-AEC lector C3 desplegado y verificado en produccion: paso 4 del orden de construccion cerrado`
- `substrato Ek-Chuah forma Q: log JSONL durable append-only + proyeccion SQLite regenerable, con el falsador I1 (borrar y reconstruir = identico) ejecutable`
- `Exportador del borde local a nube idempotente por line_sha: el unico cruce del camino B Ek-Chuah, membrane-safe (solo el log)`
- `puerta unica de mutacion del catalogo, no-destructivo por construccion`
- `La verdad es el estado observado, no los numeros heredados de procesos previos incompletos`

**Fractura viva (MODERADA) que te toca a ti.** `Camino B ...` esta **dormant** con dependientes **activos**, uno de ellos: *"El sistema AEC calco el LECTOR de concept-sediment-mcp pero divergio en la ESCRITURA: camino B (SQLite+log+replicate) vs patron una-DB — por eso el grano local no es visible en la nube"*. Ese es exactamente el incidente que motivo el **B realineado** (§7). El concepto padre no se ha refrescado. Si tocas el cruce local->nube, reactivalo al sedimentar en vez de escribir uno nuevo.

## 13. Aterrizaje

1. Lee este skill entero. Es el arranque de este repo.
2. Carga el estado vigente: cabezal del ultimo fotograma de `MEMORIA.md`, y `git log` + `git status` de este repo.
3. **Corre `cs_get_alerts`** (sistema inmunologico): fracturas y vacunas faltantes. Te dice que esta a punto de romperse antes de que lo rompas.
4. **Consulta el grafo antes de decidir** (directiva 1). Cita lo que encuentres, con la grafia exacta (§12-bis).
4. Trabaja dentro del perimetro: superficie nube. Substrato = CodeCS; CRM = Code; docs = Bibliotecario. Lo demas se pide como SOL/HANDOFF via el Guardian.
5. Cierra sedimentando.

## 14. Cierre de sesion

Cuando el Guardian diga "prepara cierre" o termine un bloque:

1. **Identifica los conceptos trabajados** (4-8 tipico, max ~10). Clasifica el `depth` con la pregunta clave: ¿se MENCIONO (`mention`, 0.3), se APLICO (`usage`, 0.7) o se DECIDIO (`decision`, 1.0)? Anti-patron frecuente: poner `pattern` o `principle` en `depth` — esos son *type*, y el type lo infiere el sistema.
2. **Gate MTV por concepto** (directiva 1): busca cada uno en el grafo antes de escribirlo. Si existe, reutiliza el nombre EXACTO (grafia, acentos). **Cero fantasmas:** todo `related_to.target` debe existir en el grafo o en el mismo YAML.
3. **Genera el YAML** en `concept-sediment/sessions/`:

```yaml
concept_sediment:
  session_id: "YYYY-MM-DD-NNN-CodeMCP"
  project: ek-chuah
  domains_active: [infrastructure, workflow_protocols]
  concepts:
    - name: "nombre descriptivo del concepto"
      depth: usage                       # mention | usage | decision
      domains: [infrastructure]
      related_to:
        - target: "concepto existente en el grafo"
          relation: derived_from
      notes: "Como se uso o descubrio en esta sesion"
  status: draft                          # SIEMPRE draft; el Guardian lo promueve
```

4. **Auto-valida** — 5 checks: sintaxis YAML limpia; `depth` valido; `session_id` coincide con el nombre del archivo; targets de `related_to` existen; dominios existen. Errores se corrigen antes de guardar; warnings se informan.
5. **VACUNA — evidencia fisica obligatoria.** El cierre es (1) generar el YAML, (2) escribirlo con la Write tool, (3) **verificar con `ls -la` que el archivo existe**, (4) confirmar al Guardian. Sin el paso 3 no hay cierre: hay confabulacion. Historial del incidente: `S060: 0 YAML. S061: sin archivo. S063: confabulacion`. Es vacuna CRITICAL abierta en `cs_get_alerts` — no la reinventes, ejecutala.
6. **Reporte transferible** — no es documentacion, es la memoria que permite a otro agente continuar sin releer todo. Lleva procedencia (directiva 2).

## 15. Glosario

| Termino | Significado |
|---|---|
| Guardian | Entheos, el humano |
| MTV | Marco Teorico Vivo: el grafo consolidado, consultado antes de actuar |
| Grano | YAML-AEC: la unidad de saber exterior que se consume al grafo |
| Roca / via | El hallazgo (bytes, nivel 1) / como se llego a el (metadato, nivel 2) |
| Referente / version | Identidad persistente (`canonical(URL)`) / `(referente, content-hash, capture_ts)` |
| Load-bearing | Afirmacion que sostiene una conclusion: exige snapshot vivo (I2) |
| WORM | Write Once Read Many: `../AEC`, un solo append-writer, fuera de todo repo |
| Camino B | La nube recibe el log y reconstruye la proyeccion aqui |
| G-pre / G-post | Devolucion antes de ingerir / revision de lo ya ingerido |
| Fotograma / cabezal | Unidad de memoria en MEMORIA.md / posicion actual |
| Sedimentar | Registrar conceptos de la sesion en el grafo via YAML |
| SOL / HANDOFF | Solicitud a otro agente / transferencia formal de tarea |
| Fantasma | Referencia a un concepto que no existe en el grafo |
| Fractura / vacuna | Alerta del sistema inmunologico del grafo |
| Colapsar | Encontrar y documentar algo que estaba en superposicion |

## 16. Donde profundizar

Los documentos fuente estan atesorados en `docs_inducop/Acervo/` (no se copian aqui — directiva 7):
`DISENO_EK_CHUAH_C0_AEC_2026-06-26.md` (diseno C0, invariantes, gobernanza) ·
`GUIA_CONSUMO_YAML_AEC_2026-07-02-CodeMCP.md` (runbook del grano) ·
`SCHEMA_YAML_AEC_2026-06-26.md` (contrato del schema) ·
`SISTEMA_EK_CHUAH_Y_GRAFO_2026-07-02-CodeMCP.md` (contexto de sistema) ·
`concept-sediment/PROTOCOLO_CIERRE_SESION.md` (esquema del YAML de cierre).
