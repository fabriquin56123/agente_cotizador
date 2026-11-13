# Ficha de Proyecto

## Qué es este proyecto

Asistente de IA que lee la solicitud de un comercio y decide **si se le cotiza, a qué tasa de comisión y por qué**. Aplica la política de pricing de la empresa con **reglas fijas en Python**, no por intuición del modelo.

- **Usuario objetivo:** analistas de Pricing que hoy revisan las solicitudes a mano. Los casos dudosos pasan a un experto.
- **Datos:** todos ficticios. No tratar nada de este repo como información real de clientes.

## Principio rector

> **El modelo explica; el motor de reglas decide.**

- Las decisiones y el cálculo de tasas viven en el motor de reglas (Python). El LLM **nunca** calcula tasas ni decide aprobar/rechazar por su cuenta.
- El agente solo puede informar **lo que devuelven las tools**. Si un dato no fue consultado, no se menciona (ej. no inventar el giro de una solicitud rechazada).

## Entradas

| Entrada | Formato | Contenido |
|---|---|---|
| Solicitud del cliente | `.txt` | RUC, razón social, giro (MCC), banco afiliado, tipo de cuenta, ubicación, tasas ofrecidas por la competencia |
| Base transaccional | CSV | Volumen mensual por cliente y por giro en BBVA, Interbank y BCP |
| Política de pricing | `.txt` | Reglas de negocio y criterios de decisión |
| Informe de rentabilidad por zonas | `.txt` | Rentabilidad por zona geográfica |
| Tarifario por MCC | archivo de tarifas | Tasa base por giro |

## Salidas

- **Decisión:** `RECHAZA`, `EVALÚA EXPERTO` o `APRUEBA`, siempre con su motivo.
- **Giro principal** y **tasa final** (entre **1.40 %** y **5.00 %**), **solo si se aprueba**.
- **Dos CSV:**
  1. Consolidado de las 15 solicitudes con su decisión.
  2. Solo las solicitudes aprobadas.
- Explicación en lenguaje natural y **registro de la decisión solo si el usuario lo confirma**.

## Arquitectura

```
Usuario → Agente (Microsoft Foundry) → 6 tools → API FastAPI (solo lectura) → Base de datos
                                          └──→ Motor de reglas (Python)
                                          └──→ Búsqueda en política (RAG local)
```

### Las 6 tools del agente

1. `leer_solicitud` — lee y estructura la solicitud (`.txt`).
2. `consultar_transacciones` — volumen mensual del cliente y por giro.
3. `consultar_comercios_similares` — comercios comparables por giro/zona.
4. `buscar_en_politica` — búsqueda en la política (RAG local, **léxica**: no entiende sinónimos).
5. `evaluar_solicitud` — invoca el motor de reglas; devuelve decisión, motivo, giro y tasa.
6. `guardar_decision` — persiste la decisión; **solo con confirmación explícita del usuario**.

### Componentes

- **Motor de reglas (Python):** única fuente de verdad para decisiones y tasas.
- **API FastAPI:** de **solo lectura** sobre la base de datos.
- **RAG local:** búsqueda en política e informe de zonas.
- **Logging:** registro de eventos **sin datos personales**.

## Reglas de negocio (supuestos a validar)

Los siguientes valores son **inventados** y deben validarse con el área de Pricing antes de cualquier uso real:

- Tarifario por MCC.
- Umbral de **giro dominante: 3×**.
- Ajuste de **+0.30 pp**.
- Recargo de **+0.20 pp** por zona premium.
- Rango de tasa final: **1.40 % – 5.00 %**.

**No cambiar estos valores sin indicación explícita.** Si se modifican, dejarlo documentado y cubierto por tests.

## Reglas para trabajar en este repo

### Lo que sí
- Mantener la lógica de decisión y de tasas **solo** en el motor de reglas, de forma determinista y testeable.
- Escribir/actualizar tests ante cualquier cambio en reglas, umbrales o tarifario.
- Mantener las instrucciones del agente alineadas con el principio: *informar solo lo que devuelven las tools*.
- Tratar los casos dudosos como `EVALÚA EXPERTO`, nunca forzarlos a aprobar o rechazar.
- Devolver siempre el motivo de la decisión.

### Lo que no
- No mover cálculo de tasas ni decisiones al prompt del modelo.
- No escribir en disco ni en la base sin confirmación explícita del usuario.
- No agregar endpoints de escritura a la API (es de solo lectura).
- No registrar datos personales (RUC, razón social, etc.) en logs.
- No presentar giro ni tasa en solicitudes rechazadas si las tools no los devolvieron.
- No usar datos reales: la API **no tiene autenticación** y solo es aceptable con datos ficticios.

## Riesgos conocidos

| Riesgo | Estado / mitigación |
|---|---|
| El modelo añade información no consultada (pasó con el giro de una solicitud rechazada) | Ajustar instrucciones del agente: informar solo lo que devuelven las tools |
| Supuestos de negocio inventados (tarifario, 3×, +0.30 pp, +0.20 pp) | Validar con Pricing |
| API sin autenticación | Aceptable con datos ficticios; agregar auth antes de datos reales |
| Escritura en disco | Controlada: solo con confirmación explícita |
| Búsqueda en política limitada (léxica, sin sinónimos) | Considerar búsqueda semántica en una siguiente etapa |

## Hoja de ruta

1. Ajustar instrucciones del agente para que informe solo lo que devuelven las tools.
2. Validar tarifario y umbrales con el área de Pricing.
3. Agregar autenticación a la API antes de usar datos reales.
4. Desplegar la API en Vercel (opcional) y probarla con el agente.
5. Evaluar con casos reales y definir el flujo de revisión del experto.

## Convenciones

- **Idioma:** documentación, mensajes de decisión y explicaciones al usuario en **español**.
- **Python:** tipado, funciones puras en el motor de reglas, sin efectos secundarios.
- **Salida de decisión:** exactamente uno de `RECHAZA`, `EVALÚA EXPERTO`, `APRUEBA`.
- **Tasa:** porcentaje con dos decimales, dentro de 1.40 %–5.00 %.
