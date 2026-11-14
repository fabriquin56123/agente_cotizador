# Agente de cotización de comisiones — Pricing · Izipay (Microsoft Foundry)

Agente empresarial que ayuda al área de Pricing a **cotizar la tasa de comisión** de un comercio
según la política de pricing, el informe de rentabilidad por zonas y la base transaccional de
clientes (expuesta por una API FastAPI de solo lectura). **Todos los datos son ficticios.**

- Reglas del proyecto: [`CLAUDE.md`](CLAUDE.md) · Criterios de terminado: [`docs/definition-of-done.md`](docs/definition-of-done.md)
- Arquitectura: [`docs/arquitectura.png`](docs/arquitectura.png) · Pruebas y resultados: [`docs/pruebas.md`](docs/pruebas.md)

## Estructura
```
Trabajo1/
├── README.md  CLAUDE.md  requirements.txt  requirements-dev.txt  .env.example  .gitignore  .python-version  pytest.ini
├── vercel.json  api/index.py          # OPCIONAL (Vercel), no se despliega solo
├── src/
│   ├── crear_agente.py   agente.py   herramientas.py        # agente Foundry + tools
│   ├── politica.py  cotizador.py  modelos.py                # reglas de negocio (puras)
│   ├── validacion.py  logging_seguro.py  config.py          # validación, logs seguros, configuración
│   ├── repositorio.py  servicios.py  solicitudes.py         # lectura de datos y solicitudes
│   ├── rag.py  instrucciones.py                             # RAG local (BM25) e instrucciones del agente
│   ├── generar_datos.py  consolidar.py                      # datos de prueba y consolidado
│   └── api/ app.py  rutas.py                                # FastAPI (solo GET)
├── data/                                                    # solo datos de prueba publicables
│   ├── politica_pricing_izipay.txt  informe_rentabilidad_zonas.txt  tarifario_mcc.csv
│   ├── transacciones_clientes.csv                           # 24 clientes, multigiro = varias filas por periodo
│   ├── solicitudes/SOL-001.txt … SOL-015.txt
│   ├── solicitudes_consolidado.csv                          # 15 solicitudes + flag + giro principal + tasa final
│   ├── resultados_cotizacion.csv                            # solo cotizaciones aprobadas
│   └── salidas/decisiones_agente.csv                        # lo escribe la tool guardar_decision (con confirmación)
├── tests/                                                   # unitarias, rechazos, e2e con 3 solicitudes
└── docs/  definition-of-done.md  arquitectura.png  pruebas.md
```

## Reproducir desde cero
Requiere **Python 3.11**.
```bash
python3.11 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python -m src.generar_datos     # (re)genera transacciones, tarifario y 15 solicitudes .txt
python -m src.consolidar        # aplica la política → consolidado + resultados (imprime una tabla)
pytest -q                       # pruebas
```

### API (solo lectura)
```bash
uvicorn src.api.app:app --reload       # http://127.0.0.1:8000/docs
```
| Ruta | Descripción |
|---|---|
| `GET /health` | Estado |
| `GET /transacciones?ruc=&periodo=&codigo_giro=&limite=&desde=` | Filas de la base (límite máx. 100) |
| `GET /clientes/{ruc}/resumen?meses=6` | Resumen por giro, sin datos personales |
| `GET /comercios-similares/{mcc}` | Tasa de referencia de comercios similares |
| `GET /tarifario` · `GET /politica/buscar?q=` | Tarifario y RAG |

Cada respuesta lleva `X-Correlation-ID`. **El agente obtiene los datos transaccionales solo por esta API** (ya no lee el CSV):
`API_BASE_URL` es obligatoria. Para evaluar una solicitud, el agente recorre `GET /transacciones` de 100 en 100 filas
(más `GET /tarifario`); el CSV queda como base de datos de la API.

### Agente en Microsoft Foundry
1. `cp .env.example .env` y completa `PROJECT_ENDPOINT`, `MODEL_DEPLOYMENT_NAME`, `AGENT_NAME` (y `MODEL_ENDPOINT`), además de `API_BASE_URL` (local: `http://127.0.0.1:8000`; Vercel: su URL). Autenticación con `az login` (azure-identity).
   Deja la API corriendo en otra terminal (`uvicorn src.api.app:app`) antes de ejecutar el agente.
2. **Plan, sin crear nada:** `python -m src.crear_agente`
3. **Crear el agente** (acción con efectos en la nube; pide confirmación escribiendo el nombre): `python -m src.crear_agente --apply`
4. Ejecutar: `python -m src.agente` (chat) o `python -m src.agente --solicitud SOL-004` (evalúa y deja el chat abierto; Enter vacío para salir).

> Los pasos 3 y 4 no se ejecutaron durante el desarrollo (sin acceso a Azure). El cliente usa la API de
> `azure-ai-projects` 2.x documentada en [Microsoft Learn](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/function-calling)
> (`create_version`, `get_openai_client(agent_name=…)`, `conversation=…`). Si tu versión instalada difiere, ajusta solo `crear_agente.py` y `agente.py`.

## Tools del agente
| Tool | Tipo | Qué hace |
|---|---|---|
| `leer_solicitud` | lectura | Datos de la solicitud SOL-NNN |
| `consultar_transacciones_cliente` | lectura (API) | Resumen de 1–12 meses por giro |
| `consultar_comercios_similares` | lectura (API) | Tasa de referencia por MCC |
| `buscar_politica` | lectura (RAG) | Fragmentos de la política e informe de zonas |
| `evaluar_solicitud` | lectura (API) | Decisión determinista según la política, con datos traídos de la API |
| `guardar_decision` | **escritura** | Requiere **confirmación explícita** del usuario (callback fuera del modelo) |

Toda entrada se valida (tipo, rango, lista permitida, longitud) antes de ejecutar. Cada llamada registra
`correlation_id`, herramienta, latencia, resultado y error; los RUC se enmascaran y no se registran secretos,
razón social ni direcciones.

## Política resumida (detalle en `data/politica_pricing_izipay.txt`)
| Regla | Resultado |
|---|---|
| DNI o RUC 10 | RECHAZA |
| Cliente de cartera sin transacciones en 6 meses | RECHAZA |
| Multigiro con giro secundario ≥ 3× el principal declarado | RECHAZA |
| Multigiro normal | Giro principal = mayor volumen (6 meses) |
| < 6 meses de historial | Tasa de comercios similares (mismo MCC) |
| Cuenta Interbank | Tasa = 0.75 × tasa más alta de la competencia |
| Límites | 1.40 % – 5.00 % |
| Tasa > competencia (fuera de zona premium) | ≤ +0.30 pp EXPERTO · > +0.30 RECHAZA |
| Tasa > competencia (zona premium*) | ≤ +0.30 pp APRUEBA · ≤ +0.60 EXPERTO · > +0.60 RECHAZA |

\*Miraflores, San Isidro, Barranco, San Borja (Lima), Trujillo, Arequipa y Cusco; además suman una prima de +0.20 pp.

## Vercel (opcional)
Resultado de la prueba: **compatible, pero no desplegado**. Vercel no ofrece Python 3.11 (usa 3.12+); el código
es compatible con 3.11 y 3.12. Archivos: `vercel.json` y `api/index.py`. **No se desplegó nada.** Si quieres
desplegar, hazlo tú tras revisar el plan: `npm i -g vercel && vercel` (verifica luego `/health`). Si prefieres no
usarlo, ignora esos dos archivos: todo funciona en local.

## Supuestos a revisar
- Interpretación A: “0.75 de la tasa más alta” = **multiplicar por 0.75**.
- “Mucho mayor” (multigiro) = 3×; “diferencia pequeña” = 0.30 pp; “cliente de cartera” = RUC con historial en la base pero sin movimientos en 6 meses; un RUC ausente de la base es “nuevo”.
- Con varias ofertas de competencia, la referencia es la **más alta**.
- Prima de zona premium de +0.20 pp (derivada del informe de rentabilidad); el tarifario y los descuentos por volumen son inventados.
- `resultados_cotizacion.csv` incluye solo APRUEBA; los casos EVALUA_EXPERTO quedan en el consolidado.
