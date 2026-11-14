# Definition of Done

Una entrega se considera terminada solo si **todos** los puntos se cumplen.

## 1. Restricciones obligatorias
- [ ] Python 3.11 declarado (`.python-version`); `requirements.txt` con
      `azure-ai-projects>=2.10.0,<3.0.0` y `azure-identity>=1.27.0,<2.0.0`.
- [ ] Toda tool de lectura se ejecuta sin fricción; toda tool de escritura queda
      **bloqueada** sin confirmación explícita (test de rechazo incluido).
- [ ] Cada tool valida tipo, rango, lista permitida y longitud antes de ejecutar.
- [ ] Cada llamada a tool registra `correlation_id`, tool, latencia, resultado y error.
      Ningún log contiene secretos ni datos personales (test que lo verifica).
- [ ] Ningún despliegue ni recurso con costo se ejecutó sin plan aprobado.
- [ ] Funciones pequeñas (≤ ~30 líneas), tipadas y con prueba.

## 2. Datos
- [ ] `data/transacciones_clientes.csv`: ≥ 20 clientes distintos (incluye a los de las
      15 solicitudes), columnas: id_transaccion, id_cliente, ruc, razon_social,
      periodo, codigo_giro, moneda (PEN/USD), volumen_bbva, volumen_interbank,
      volumen_bcp; hay periodos con más de un registro (multigiro).
- [ ] 15 solicitudes `.txt` formales y breves + `solicitudes_consolidado.csv` (≥ 15 filas)
      con flag `RECHAZA | EVALUA_EXPERTO | APRUEBA`, giro principal y tasa final
      (solo si se aprueba).
- [ ] `resultados_cotizacion.csv` contiene **solo** clientes con cotización aprobada.
- [ ] `politica_pricing_izipay.txt` e `informe_rentabilidad_zonas.txt` existen y el RAG
      los recupera.

## 3. Reglas de política verificadas por prueba
- [ ] DNI o RUC 10 → RECHAZA.
- [ ] Cliente de cartera sin transacciones en los últimos 6 meses → RECHAZA.
- [ ] Multigiro con giro secundario ≥ 3× el principal declarado → RECHAZA.
- [ ] Multigiro normal → giro principal = mayor volumen de los últimos 6 meses.
- [ ] < 6 meses de historial → tasa de referencia de comercios similares (mismo MCC).
- [ ] Cuenta Interbank → tasa = 0.75 × tasa más alta de la competencia.
- [ ] Toda tasa final entre 1.40 % y 5.00 %.
- [ ] Tasa > competencia: umbrales fuera / dentro de zonas premium según tabla.

## 4. Servicios
- [ ] API FastAPI de solo lectura (solo GET) sirve el CSV; validación de parámetros.
- [ ] El agente obtiene las transacciones solo por la API (paginando); no lee el CSV (test).
- [ ] `crear_agente.py` es `--dry-run` por defecto; `--apply` pide confirmación.
- [ ] Prueba de compatibilidad con Vercel documentada (resultado explícito).

## 5. Calidad y documentación
- [ ] `pytest -q` en verde (los tests que requieren FastAPI/Azure se omiten con
      `importorskip` si el paquete no está instalado).
- [ ] 3 solicitudes de prueba (1 multigiro) documentadas en `docs/pruebas.md`.
- [ ] `README.md` permite reproducir todo desde cero.
- [ ] `.env` no está en el entregable; `.env.example` sin valores.
