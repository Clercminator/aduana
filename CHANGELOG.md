# Changelog

Historial de cambios funcionales del prototipo. El estado vigente, los flujos y las
limitaciones se documentan en `README.md`.

## 26-08-2026 — Compuertas de extracción e implementación híbrida

- Un documento sin extracción exitosa, un tipo requerido ausente o una clasificación bajo
  el umbral ya no puede terminar como trabajo exitoso. El trabajo queda `needs_review`, el
  despacho `review_required` y, si falta integridad documental, no se genera un cálculo nuevo.
- Los campos financieros y de decisión definidos por cliente tienen un umbral de confianza
  versionado. Un valor ausente o bajo el umbral permite como máximo un cálculo provisional,
  exige corrección humana con motivo y bloquea Excel/DIN con HTTP 409.
- `hybrid` es el backend normal: solo usa el parser local cuando el YAML del cliente declara
  una plantilla y el contenido coincide; cualquier layout no reconocido cae a OpenRouter.
  `local` sigue disponible para QA determinista y `openrouter` para forzar IA en todo el lote.
- En PDFs escaneados, las anotaciones OCR devueltas durante clasificación se reenvían en la
  conversación de extracción. Así se evita pedir una segunda conversión OCR cuando el
  proveedor entrega una anotación reutilizable; el hecho queda registrado en telemetría.
- La UI y la hoja `Trazabilidad` de Excel identifican el resultado como
  `Extracción local determinista — demo` o `Extracción con IA — OpenRouter`, además de
  registrar proveedor, parser/modelo y resultado de la compuerta.

## 25-08-2026 — Preparación multiagencia y carga segura

- La demo incluye dos agencias sintéticas seleccionables: **IMR Demo** y **Pacífico Demo**.
  Cada una carga su propia organización, cliente, branding, póliza y defaults desde YAML;
  cambiar de agencia no requiere modificar código.
- Los escenarios A/B/C/D están declarados por agencia y solo habilitados para IMR Demo,
  porque sus documentos pertenecen a Falabella. UI y API impiden aplicar accidentalmente
  la póliza de Pacífico a esos fixtures; Pacífico sí admite cargas PDF propias.
- Todas las rutas de negocio exigen contexto de organización (`X-Org-ID`; `org_id` en enlaces
  descargables), consultan recursos por `org_id` y tienen pruebas que bloquean el acceso
  cruzado. Es una frontera demostrable de datos, no autenticación productiva.
- Los documentos y artefactos se separan por organización y las versiones de cliente
  pertenecen explícitamente a una organización en la base.
- El intake acepta solo PDFs válidos y aplica límites configurables de cantidad, tamaño por
  archivo, tamaño del lote y páginas, antes de crear el despacho. Los errores se muestran en
  la interfaz con un mensaje concreto.
- GitHub Actions ejecuta formato/lint, las 64 pruebas Python actuales, build y auditoría del
  frontend, y el E2E completo contra API, worker y PostgreSQL en una pila Docker aislada.

## 24-08-2026 — Reglas confirmadas y exactitud financiera

- Una factura equivale a un parcial y a una DIN. El cálculo sigue siendo uno por B/L, pero
  `din.json` devuelve un array y `din.pdf` contiene una declaración por factura.
- Toda factura se normaliza primero a FOB según `incoterm_rules`; CIF/CFR y similares deben
  traer el desglose requerido en `included_amounts`. Si falta, la valoración se bloquea con
  una excepción crítica y nunca estima el componente.
- El seguro es configuración versionada del cliente. Falabella usa `policy_rate` de
  `0.000462`; el certificado se conserva para EXC-04 y no alimenta el cálculo. Los modos
  `certificate` y `theoretical` también están implementados; el segundo permanece bloqueado
  mientras la tasa teórica esté en `null`.
- El 115 % de CFR sigue marcado como **inferido y pendiente de confirmación**. No presentarlo
  como hecho confirmado.
- El FX chileno es dólar aduanero mensual y se valida contra el mes de aceptación de la DIN.
  La demo fija una fila mensual manual y ficticia; todavía no integra la fuente productiva.
- IVA está marcado `recoverable: true`: se paga en la vista declaración, pero se excluye del
  costo puesto. Excel expone ambas vistas por separado.
- EXC-12 compara la suma de facturas con `BillOfLading.declared_value_total`; si el B/L no
  trae ese dato queda `SKIPPED`, y si difiere el resultado es `CRITICAL`.
- Scenario C contiene 45 PDFs y 40 facturas/DIN; Scenario D prueba equivalencia CIF→FOB;
  Scenario E es un pack de QA separado con 12 facturas de proveedores/layouts distintos y
  dos certificados de origen. Dos de esas facturas son PDFs de foto sin capa de texto.
