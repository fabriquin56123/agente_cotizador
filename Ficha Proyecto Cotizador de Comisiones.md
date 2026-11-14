# Ficha breve: Agente Cotizador de Comisiones

Nov 13, 2026 · @Fabrizzio

Un asistente de IA que revisa la solicitud de un comercio y responde si se le puede cotizar, a qué tasa de comisión y por qué.

## Nombre

**Agente Cotizador de Comisiones**, del área de Pricing y Optimización de Precios de Izipay.

## Usuario objetivo

Analistas de Pricing que hoy revisan las solicitudes una por una. Los casos dudosos se derivan a un experto.

## Entradas

El agente trabaja con tres fuentes; todos los datos del proyecto son ficticios.

- **La solicitud del comercio:** quién es, a qué se dedica, en qué banco recibe sus cobros, dónde está y qué tasa le ofreció la competencia.
- **El historial de ventas del comercio** de los últimos 6 meses, consultado a través de un servicio de datos.
- **La política de pricing de la empresa**, con su tarifario y un informe de las zonas donde se pueden cobrar tasas más altas.

## Salidas

Por cada solicitud, el agente entrega una decisión explicada y deja dos archivos de resultados.

- **Una decisión clara:** se rechaza, pasa a un experto o se aprueba, siempre con su motivo.
- **Si se aprueba:** el giro principal del negocio y la tasa final, entre 1.40 % y 5.00 %.
- **Dos archivos de resultados:** uno con las 15 solicitudes de prueba y su decisión, y otro solo con las aprobadas.
- **Una explicación en lenguaje sencillo**, y el guardado de la decisión solo si el usuario lo confirma.

## Herramientas

Un agente conversa con el usuario, pero las decisiones las toma un motor de reglas, no el criterio del modelo.

- **Un agente de IA en Microsoft Foundry**, con el que se conversa.
- **Un motor de reglas** que aplica la política y calcula las tasas.
- **Un servicio de datos** con el historial de ventas de los comercios.
- **Un buscador de la política**, para responder preguntas como "¿por qué se rechaza un RUC 10?".
- **Un registro de actividad** que no guarda datos personales ni claves.

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
