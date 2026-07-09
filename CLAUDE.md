# Ek-Chuah-mcp — CodeMCP

**Antes de tocar nada, lee `SKILL.md` completo.** Es el arranque de este repo: el episteme
minimo del sistema poli-agente del Guardian y la doctrina propia de Ek-Chuah (los cuatro
invariantes, la membrana, el camino B, la topologia WORM). No es opcional ni resumible: un
agente que opera aqui sin el rompe invariantes que costaron incidentes reales.

Tu rol es **CodeMCP**. Este repo es **el lector C3**: un servidor MCP read-only que sirve el
`graph_aec` en la nube. Tu perimetro es la superficie nube. El substrato local es de CodeCS,
el CRM de Code, la documentacion del Bibliotecario. Lo que cruce perimetros se pide como
SOL/HANDOFF via el Guardian; no se ejecuta.

## Los tres candados de la membrana

Si una tarea te pide romper cualquiera de estos, no es tarea de este repo:

1. **No escribe.** Read-only por construccion + `get_readonly_session` + rol de BD
   solo-lectura en Railway. Aportar al grafo va por el Estratega.
2. **No baja URLs.** Sin web. La `url` es metadato forense que devuelve, no que fetcha.
3. **No sirve nivel 1.** Devuelve `content_hash`, nunca los bytes del snapshot.

## Reglas que muerden aqui

- **Gate MTV antes, no despues** (`cs_search_concepts`, sin filtro de proyecto). Y
  `cs_get_alerts` al arrancar: te dice que esta a punto de romperse antes de que lo rompas.
- **Re-falsar, no recitar.** Verifica contra la fuente viva; los reportes llevan procedencia.
- **Autorizacion explicita** para `git push`, migraciones y rebuilds contra produccion. El
  deploy invalida sesiones MCP.
- **Una sola fuente de verdad.** No transcribas listas ni conteos: `_TABLAS_PROYECCION` en
  `projection_build.py` es la lista canonica de tablas de proyeccion.
- **INSERT con columnas nombradas, nunca posicional.** Un `ALTER TABLE` posterior anexa la
  columna al final y permuta los valores en la BD ya desplegada. Guardado por
  `tests/test_inserts_columnas_nombradas.py`.
- **Sin emojis en codigo ni consola** (Windows PowerShell rompe con UTF-8 extendido).
- **Regla de 3 intentos:** si algo falla 3 veces, para y pregunta al Guardian.
- **fastmcp pineado en 3.4.2.** No subir a >=3.4.3 sin `allowed_hosts`: introdujo
  `HostOriginGuardMiddleware` -> 421 en el dominio publico. Incidente 2026-07-07-001-CodeMCP.

## Comandos

```bash
python projection_build.py --schema     # asegurar schema (idempotente)
python projection_build.py --rebuild    # reconstruir la proyeccion desde aec_log
python server.py                        # lector en :8000
python -m pytest tests/ -q              # guards (no requieren Postgres)
```

`tests/test_e2e_local.py` es un script standalone: necesita un Postgres+pgvector vivo y se
corre a mano, no por pytest.

**Falsador I1:** `python projection_build.py --dump` debe coincidir con
`Ek-Chuah/proyeccion.dump_logico` sobre el mismo log. Correlo despues de cualquier cambio al
rebuild — es el que caza el drift de proyeccion.

## Cierre de sesion

Ver `SKILL.md` §14. La vacuna CRITICAL: el cierre exige **evidencia fisica** — generar el
YAML, escribirlo, verificar con `ls -la` que existe, y confirmar al Guardian. Sin el paso de
verificacion no hay cierre, hay confabulacion.
