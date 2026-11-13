# Pruebas

Fecha de referencia de los datos: **2026-11-12** (ventana de 6 meses: 2026-05 a 2026-10).
Todos los datos son ficticios.

## 1. Cómo se ejecutaron
```bash
python -m src.generar_datos && python -m src.consolidar
pytest -q
```
Resultado en el entorno de desarrollo: **166 pruebas OK, 2 omitidas**. Las omitidas son las que
requieren `fastapi`/`httpx` (`tests/test_api.py` y el entrypoint de `tests/test_vercel_compat.py`);
no estaban instalados ni se pudieron instalar en ese entorno (sin red). **Ejecútalas tú** con
`pip install -r requirements-dev.txt && pytest -q`.

No se ejecutó contra Microsoft Foundry real (no se creó ningún agente ni se hicieron llamadas a la nube):
los tests del agente usan un cliente simulado.

## 2. Tres solicitudes de prueba (`tests/test_e2e_3_solicitudes.py`)

| Caso | Qué valida | Resultado |
|---|---|---|
| **SOL-001** (Interbank, San Isidro) | Tasa = 0.75 × la más alta de la competencia (BBVA 2.80 %, BCP 3.00 %) | APRUEBA · 5411 · **2.25 %** |
| **SOL-004** (múltiples giros 5812 + 5814, Cusco, BCP) | Giro principal = mayor volumen de 6 meses (5814: S/ 912,257 vs 5812: S/ 531,883; relación 1.7×, menor que 3×). Tarifario 2.70 % − 0.10 pp (volumen) + 0.20 pp (zona premium) | APRUEBA · 5814 · **2.80 %** (competencia 3.30 %) |
| **SOL-006** (RUC 10, Trujillo) | Rechazo por documento | RECHAZA · `RUC10_NO_PERMITIDO` · sin tasa |

En las tres, `guardar_decision` queda **bloqueada** sin confirmación y solo escribe con confirmación explícita.

## 3. Casos de rechazo y borde cubiertos (`tests/test_politica.py`, `tests/test_herramientas.py`)
- DNI, RUC 10 y documento que no es de empresa → RECHAZA.
- Cliente de cartera sin transacciones en los últimos 6 meses → RECHAZA.
- Giro secundario ≥ 3× el principal declarado → RECHAZA.
- Tasa sobre la competencia: tabla de tolerancias completa (fuera de zona premium y en zona premium) en sus bordes (0.00, 0.30, 0.31, 0.60, 0.61 pp).
- Piso 1.40 % y techo 5.00 %; sin competencia informada; MCC sin tarifa → EVALUA_EXPERTO.
- Tools: id con path traversal, argumentos extra (el modelo no puede “autoconfirmar”), tipos y rangos inválidos, tool desconocida, JSON malformado.
- Logs: sin RUC completo, razón social, direcciones, correos ni tokens.

## 4. Resultado de las 15 solicitudes (`data/solicitudes_consolidado.csv`)

| Solicitud | Banco afiliado | Distrito | MCC | Competencia (%) | Decisión | Motivo | Giro principal | Tasa final (%) |
|---|---|---|---|---|---|---|---|---|
| SOL-001 | INTERBANK | San Isidro | 5411 | 2.80,3.00 | APRUEBA | TASA_MENOR_COMPETENCIA | 5411 | 2.25 |
| SOL-002 | BBVA | Miraflores | 5812 | 3.20 | APRUEBA | TASA_MENOR_COMPETENCIA | 5812 | 3.00 |
| SOL-003 | BCP | Santiago de Surco | 5912 | 2.20 | APRUEBA | TASA_MENOR_COMPETENCIA | 5912 | 2.05 |
| SOL-004 | BCP | Cusco | 5812,5814 | 3.30 | APRUEBA | TASA_MENOR_COMPETENCIA | 5814 | 2.80 |
| SOL-005 | SCOTIABANK | Arequipa | 5651,5732 | 3.50 | RECHAZA | GIRO_SECUNDARIO_DOMINANTE | - | - |
| SOL-006 | BCP | Trujillo | 5942 | 3.00 | RECHAZA | RUC10_NO_PERMITIDO | - | - |
| SOL-007 | BBVA | San Juan de Lurigancho | 7230 | 3.80 | RECHAZA | DNI_NO_PERMITIDO | - | - |
| SOL-008 | SCOTIABANK | Ate | 5251 | 2.70 | RECHAZA | CARTERA_SIN_TRANSACCIONES_6M | - | - |
| SOL-009 | BBVA | Barranco | 5812 | 3.40 | APRUEBA | TASA_MENOR_COMPETENCIA | 5812 | 3.03 |
| SOL-010 | INTERBANK | Trujillo | 5942 | 3.20 | APRUEBA | TASA_MENOR_COMPETENCIA | 5942 | 2.40 |
| SOL-011 | BCP | Cusco | 7011 | 3.00,3.10 | APRUEBA | TASA_EQUIPARABLE_ZONA_PREMIUM | 7011 | 3.23 |
| SOL-012 | BBVA | Los Olivos | 5651 | 2.90 | EVALUA_EXPERTO | SOBRE_COMPETENCIA_DENTRO_TOLERANCIA | 5651 | - |
| SOL-013 | BCP | Comas | 7230 | 2.60 | RECHAZA | SIN_MARGEN_SOBRE_COMPETENCIA | 7230 | - |
| SOL-014 | INTERBANK | San Borja | 8011 | 1.90,2.00 | APRUEBA | TASA_MENOR_COMPETENCIA | 8011 | 1.50 |
| SOL-015 | INTERBANK | Ate | 5541 | 1.30 | EVALUA_EXPERTO | SOBRE_COMPETENCIA_DENTRO_TOLERANCIA | 5541 | - |

`data/resultados_cotizacion.csv` contiene solo las 8 solicitudes aprobadas.

## 5. Prueba de compatibilidad con Vercel
Resultado: **compatible en principio, no desplegado**.
- Vercel soporta Python 3.12 (por defecto), 3.13 y 3.14; **no 3.11**. El código es compatible con 3.11
  (verificado con `ast.parse(feature_version=(3, 11))`) y en Vercel correría en 3.12+.
- La API es de solo lectura (solo GET), no escribe a disco y no registra en archivo → apta para un sistema de archivos de solo lectura.
- `vercel.json` incluye `data/**` en la función y reescribe todo a `api/index.py`.
- Pendiente (requiere tu aprobación porque es un despliegue): `vercel deploy` de prueba y verificar `/health`.
