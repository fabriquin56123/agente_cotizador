# CLAUDE.md — Agente de cotización de comisiones (Pricing · Izipay)

Guía para cualquier asistente de código que trabaje en este repositorio.

## Qué es este proyecto
Agente empresarial en **Microsoft Foundry** que ayuda al área de Pricing y
Optimización de Precios a cotizar la tasa de comisión de un comercio según:
1. la política de pricing (`data/politica_pricing_izipay.txt`),
2. el informe de rentabilidad por zonas (`data/informe_rentabilidad_zonas.txt`),
3. la base transaccional de clientes (`data/transacciones_clientes.csv`), expuesta
   por una **API FastAPI de solo lectura**.

Todos los datos son **ficticios** y publicables. No usar datos reales de clientes.

## Restricciones obligatorias (no negociables)
1. Python **3.11**; `azure-ai-projects>=2.10.0,<3.0.0`; `azure-identity>=1.27.0,<2.0.0`.
   El código debe ser compatible con 3.11 (nada de sintaxis exclusiva de 3.12+).
2. **Lecturas automáticas; toda escritura exige confirmación explícita del usuario.**
   La confirmación sale de un callback fuera del modelo; el modelo nunca la aporta.
3. **Validar** tipos, rangos, listas permitidas y longitud **antes** de ejecutar una tool
   (`src/validacion.py`).
4. **Registrar** `correlation_id`, herramienta, latencia, resultado y error.
   **Nunca** registrar secretos ni datos personales (RUC se enmascara; razón social,
   dirección, tokens y claves se redactan). Ver `src/logging_seguro.py`.
5. RAG y APIs reales permitidos; los documentos de prueba viven en `data/`.
6. Funciones **pequeñas, tipadas y probables** (puras cuando sea posible).
7. **No ejecutar despliegues ni crear recursos con costo** (agente en Foundry, Vercel,
   vector stores) sin mostrar el plan y obtener aprobación explícita.
8. Incluir pruebas unitarias, casos de rechazo y README reproducible.

## Reglas de trabajo
- Nunca leer, imprimir, copiar ni registrar el contenido de `.env`. Solo `.env.example`
  (sin valores). `.env` está en `.gitignore` y no se incluye en zips.
- El agente obtiene las transacciones **solo por la API** (`FuenteApi` en `src/herramientas.py`); no debe importar
  `repositorio` ni `servicios` (lo verifica `tests/test_fuente_api.py`). Los tests usan `FuenteDePrueba`.
- La lógica de negocio vive en módulos puros (`politica.py`, `cotizador.py`); la API,
  las tools y el agente son capas finas encima.
- Las tasas se manejan con `Decimal` (2 decimales, `ROUND_HALF_UP`), en puntos
  porcentuales (2.25 = 2.25 %).
- Cualquier cambio de política se hace en `data/politica_pricing_izipay.txt` **y** en
  `ParametrosPolitica` (`src/modelos.py`); `tests/test_consolidar.py` verifica que el
  tarifario del txt coincida con `data/tarifario_mcc.csv`.
- Los CSV de `data/` se regeneran con `python -m src.generar_datos` y
  `python -m src.consolidar`; no editarlos a mano.

## Comandos
```bash
python -m venv .venv && source .venv/bin/activate     # Python 3.11
pip install -r requirements.txt -r requirements-dev.txt
python -m src.generar_datos      # datos de prueba
python -m src.consolidar         # consolidado + resultados
pytest -q                        # pruebas
uvicorn src.api.app:app --reload # API local
python -m src.crear_agente       # dry-run (no crea nada)
```

## Mapa del código
`config` → `validacion` → `repositorio` → `cotizador` → `politica` → `consolidar`
· `rag` · `herramientas` (registro de tools) → `agente` / `crear_agente` · `api/`.
