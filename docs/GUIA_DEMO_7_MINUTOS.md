# Guion de demostración — 7 minutos

## Objetivo

Demostrar que el trabajo hoy concentrado en `PRORRATEO MASTER.xlsx` puede convertirse en un flujo trazable: documentos sin ordenar, extracción con evidencia, controles cruzados, prorrateo, revisión y una copia completada del archivo conocido por la usuaria.

El objetivo de esta reunión no es afirmar que las reglas aduaneras o el mapeo DIN ya fueron validados. Es confirmar que el flujo se parece a su trabajo, descubrir diferencias y acordar cómo validar un caso real anonimizado.

## Antes de comenzar

- Abra `PRORRATEO MASTER.xlsx` y la aplicación.
- Confirme que **IMR Demo** esté seleccionada antes de recorrer los números conocidos.
- Use únicamente los escenarios sintéticos incluidos.
- Empiece con el escenario A y luego reinicie para mostrar el escenario B.
- No muestre arquitectura, modelos ni costos del proveedor salvo que se lo pregunten.

## 0:00–0:45 — Partir desde su herramienta

Muestre brevemente el archivo original.

> “Partimos desde el Excel que ustedes ya usan. La idea no es obligarlos a abandonar de inmediato una herramienta conocida, sino automatizar la preparación de los datos y devolver una copia completada y auditable.”

Abra la aplicación y señale el flujo visible: documentos, extracción con evidencia, controles, prorrateo y Excel.

Si conviene demostrar que la base no está amarrada a una sola agencia, dedique como máximo
20–30 segundos al selector: cambie a **Pacífico Demo**, muestre que cambian cliente, colores,
póliza y defaults, y vuelva a **IMR Demo** antes de cargar el escenario A.

> “El mismo motor puede cargar una configuración versionada distinta por agencia, sin
> reescribir la aplicación. Esta pantalla demuestra la separación básica; usuarios, roles,
> onboarding y facturación todavía son trabajo de producto.”

## 0:45–1:35 — Cargar documentos sin ordenar

Seleccione **Escenario A · limpio**.

> “El sistema recibe una instrucción y siete documentos del embarque sin depender de sus nombres. Los clasifica, extrae los campos necesarios y conserva la página y el texto que respaldan cada valor.”

Durante el progreso, mencione que el tiempo, el modelo y el costo quedan registrados. No detenga la presentación en los detalles técnicos.

Si le preguntan por archivos inválidos, la carga permite solo PDF y muestra los límites de
cantidad, tamaño y páginas. No haga una prueba improvisada durante el guion principal.

## 1:35–2:35 — Revisar evidencia

En el expediente completo, seleccione una factura o el certificado de seguro.

> “No pedimos que la usuaria confíe ciegamente en la extracción. Cada dato importante muestra su fuente, página, texto literal y confianza.”

Abra una cita en el visor PDF y señale la prima impresa del seguro.

Aclare que para Falabella esa prima es evidencia y control; el cálculo usa la tasa anual
versionada del perfil del cliente. La base de cobertura 115 % todavía figura como inferida.

> “La evidencia original no se modifica. Si una persona corrige un valor, se registra el motivo y se crea un nuevo cálculo.”

## 2:35–3:25 — Mostrar el resultado limpio

Señale los **12 controles provisionales conformes**, el prorrateo y los totales.

> “La inteligencia artificial lee los documentos. Las conciliaciones, asignaciones, redondeos y tributos se calculan con reglas deterministas y versionadas.”

No presente estos doce controles como reglas aprobadas para producción. Aunque los cambios de
dominio vienen de la conversación con la agencia, todavía deben validarse con casos reales.

## 3:25–4:45 — Mostrar detección de problemas

Pulse **Nuevo despacho** y luego **Escenario B · 7 alertas**.

> “Ahora usamos documentos que contienen errores plantados. El sistema conserva lo que dicen los documentos, continúa el cálculo según esos valores y marca el resultado como pendiente de revisión.”

Abra una alerta crítica, muestre sus fuentes y señale el impacto financiero cuando esté disponible.

> “Aquí está el valor adicional: no se trata solo de copiar datos desde un PDF. También se cruzan documentos, se explica la discrepancia y se cuantifica su posible efecto.”

## 4:45–5:35 — Corregir y dejar trazabilidad

Edite un campo, escriba un motivo breve y guarde.

> “La corrección no borra la extracción original. Genera un nuevo cálculo y deja una trazabilidad de quién cambió qué y por qué.”

Si muestra la aceptación de riesgo, aclare:

> “Esta aceptación es únicamente una función de auditoría para la demostración; no representa autorización aduanera.”

## 5:35–6:20 — Volver al Excel conocido

Pulse **PRORRATEO MASTER completado** y abra la descarga.

> “La salida conserva las hojas ‘Prorrateo General’ y ‘Prorrateo resumen’, completa sus campos y agrega documentos, extracciones, validaciones, tributos, trazabilidad y vistas separadas de declaración y costo.”

Muestre primero las dos hojas conocidas. Las hojas nuevas son respaldo, no el centro de la historia.

## 6:20–7:00 — Cerrar con validación, no con una promesa

Muestre que se genera una DIN por factura y señale la marca de borrador. No la describa como
formulario oficial ni como capacidad de presentación electrónica.

> “Esto demuestra una dirección viable, pero todavía necesitamos validar sus documentos reales, sus excepciones habituales y el significado exacto de cada campo del Excel.”

Pregunte:

1. ¿Estos son los tipos de documentos que recibe normalmente?
2. ¿Qué campos del Excel completa manualmente y cuáles ya son fórmulas?
3. ¿Qué diferencias o errores consumen más tiempo?
4. ¿Qué tendría que producir el sistema para que un despacho se considere listo?
5. ¿Podemos validar el siguiente paso con un despacho histórico completamente anonimizado, después de acordar privacidad y tratamiento de datos?

## Límites que deben decirse explícitamente

- Los documentos del demo son sintéticos; las imágenes de referencia solo orientan sobre familias y formatos documentales.
- Los doce controles, las reglas fiscales y el mapeo DIN son provisionales.
- El dólar aduanero del demo es mensual, ficticio y manual.
- La base de cobertura de seguro 115 % y la tasa teórica siguen pendientes de confirmación.
- El sistema no presenta declaraciones ni concede autorizaciones.
- El selector y el aislamiento por organización son de demostración. `X-Org-ID` todavía no
  es autenticación; faltan login, membresías, roles y defensa de base de datos para SaaS real.
- No deben cargarse documentos reales hasta aprobar privacidad, retención y condiciones del proveedor.
