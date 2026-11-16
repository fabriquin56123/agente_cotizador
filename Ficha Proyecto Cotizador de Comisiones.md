# Ficha breve: Agente Cotizador de Comisiones

Nov 13, 2026 · @Fabrizzio

Un asistente de IA que revisa la solicitud de un comercio y responde si se le puede cotizar, a qué tasa de comisión y por qué.

## Nombre

**Agente Cotizador de Comisiones**, del área de Pricing y Optimización de Precios de una empresa de medios de procesos de pago.

## Usuario objetivo

Analistas de Pricing que hoy revisan las solicitudes una por una. Los casos dudosos se derivan a un experto.

## Entradas

El agente trabaja con tres fuentes; todos los datos del proyecto son ficticios.

- **La solicitud del comercio:** quién es, a qué se dedica, en qué banco recibe sus cobros, dónde está y qué tasa le ofreció la competencia.
- **El historial de ventas del comercio** de los últimos 6 meses, consultado a través de un servicio de datos.
- **La política de pricing de la empresa**, con su tarifario y un informe de las zonas donde se pueden cobrar tasas más altas.

## Salidas

Por cada solicitud, el agente entrega una decisión explicada y el archivo de resultado.

- **Una decisión clara:** se rechaza, pasa a un experto o se aprueba, siempre con su motivo.
- **Si se aprueba:** el giro principal del negocio y la tasa final, entre 1.40 % y 5.00 %.
- **Una explicación en lenguaje sencillo**.
- **Archivo de resultados:** los resultados de la evaluación del agente guardados si el usuario lo confirma.

## Componentes y herramientas

Un asistente de IA conversa con el usuario, pero las decisiones las toma un motor de reglas, no el criterio del modelo.

**Componentes**

- **Asistente de IA en Microsoft Foundry:** entiende la consulta, elige qué herramienta usar y redacta la respuesta.
- **Motor de reglas:** aplica la política y calcula las tasas. Siempre da el mismo resultado con los mismos datos.
- **Servicio de datos (API de solo lectura):** entrega el historial de ventas de los comercios y el tarifario.
- **Buscador de la política:** responde preguntas como "¿por qué se rechaza un RUC 10?".
- **Registro de actividad:** deja constancia de cada acción sin guardar datos personales ni claves.

**Herramientas**

Son las seis acciones que el asistente puede pedir. Las ejecuta el código del proyecto, no Foundry.

| Herramienta | Qué hace | Tipo |
|---|---|---|
| Leer solicitud (`leer_solicitud`) | Trae los datos de una solicitud: giros, banco, ubicación y tasas de la competencia | Lectura |
| Consultar ventas del cliente (`consultar_transacciones_cliente`) | Resume sus ventas por giro en los últimos meses | Lectura |
| Consultar comercios similares (`consultar_comercios_similares`) | Obtiene la tasa de referencia de comercios del mismo rubro, útil para clientes nuevos | Lectura |
| Buscar en la política (`buscar_politica`) | Encuentra los fragmentos de la política y del informe de zonas que responden la pregunta | Lectura |
| Evaluar solicitud (`evaluar_solicitud`) | Aplica la política y devuelve la decisión (aprueba, rechaza o pasa a experto), el giro principal y la tasa final | Lectura (calcula, no guarda nada) |
| Guardar decisión (`guardar_decision`) | Registra la decisión en el archivo de resultados | **Escritura**, requiere confirmación del usuario |

## Riesgos

El riesgo principal es que el agente agregue datos que no consultó; los demás son de reglas de prueba y de seguridad.

- **Respuestas con datos no verificados.** El agente a veces agrega información que no consultó; hay que ajustar sus instrucciones.
- **Reglas inventadas.** El tarifario y varios umbrales son de prueba y deben validarse con Pricing antes de usarlos de verdad.
- **Servicio de datos abierto.** Hoy no pide ninguna clave de acceso; con datos reales sería un riesgo.
- **Guardado de decisiones.** Está controlado: solo se guarda con confirmación del usuario.

## Siguientes pasos

1. Ajustar las instrucciones del agente para que informe solo lo que consulta.
2. Validar con Pricing el tarifario y los umbrales.
3. Proteger el servicio de datos con una clave antes de usar información real.
4. Publicar el servicio de datos en internet (opcional) y probarlo con el agente.
5. Probar con solicitudes reales y definir cómo trabaja el experto con los casos derivados.
6. Validar los datos del cliente de la solicitud con el registro RUC del portal de la SUNAT.
