import { expect, test } from "@playwright/test";
import path from "node:path";

const fixtureRoot = path.resolve("..", "fixtures");
const screenshotRoot = process.env.QA_SCREENSHOT_DIR;

test("carga múltiple, revisión, corrección, aceptación y exportaciones", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: /documentos dispersos/i })).toBeVisible();
  await page.getByRole("button", { name: "Ayuda" }).click();
  await expect(page.getByRole("heading", { name: "Guía de demostración" })).toBeVisible();
  await page.getByRole("button", { name: "Entendido" }).click();
  const cleanFiles = [
    "00_INSTRUCCION_DESPACHO_700611.pdf", "01_BILL_OF_LADING_OLS-SHA-2601147.pdf",
    "02_1_COMMERCIAL_INVOICE_BN26010441.pdf", "02_2_COMMERCIAL_INVOICE_BN26010442.pdf",
    "02_3_COMMERCIAL_INVOICE_BN26010443.pdf", "03_PACKING_LIST_OLS-SHA-2601147.pdf",
    "04_CERTIFICADO_SEGURO_MC-2026-04417.pdf", "05_CERTIFICATE_OF_ORIGIN_C26CL0114772.pdf",
  ].map((name) => path.join(fixtureRoot, "scenario_A_clean", name));
  await page.locator('input[type="file"]').nth(1).setInputFiles(cleanFiles);
  await expect(page.getByRole("heading", { name: "700611", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("12 controles provisionales conformes")).toBeVisible();
  await expect(page.getByText("8 de 8 archivos requeridos")).toBeVisible();
  await expect(page.getByText("CLP 10.659.495")).toBeVisible();

  await page.getByRole("button", { name: /nuevo despacho/i }).click();
  await page.getByRole("button", { name: /escenario b/i }).click();
  await expect(page.getByRole("heading", { name: "700612", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("3 críticas")).toBeVisible();
  await expect(page.getByText("4 advertencias")).toBeVisible();
  await expect(page.getByText("CLP 13.217.811")).toBeVisible();

  await page.getByRole("button", { name: /certificado de seguro/i }).click();
  await expect(page.getByText("Prima impresa", { exact: true })).toBeVisible();
  await page.getByTitle("Editar Prima impresa").click();
  await page.getByLabel("Motivo de la corrección").fill("Verificación del contacto durante la revisión");
  await page.getByRole("button", { name: /guardar y recalcular/i }).click();
  await expect(page.getByRole("heading", { name: "700612", exact: true })).toBeVisible({ timeout: 60_000 });

  const firstException = page.locator(".exception-card").first();
  await firstException.locator(".exception-main").click();
  await firstException.getByRole("button", { name: "Ver fuente 1" }).click();
  await expect(page.locator(".document-item.selected")).toContainText("Packing list");
  await expect(page.getByText(/Página 1 de/)).toBeVisible();
  await firstException.getByRole("button", { name: /aceptar riesgo de demo/i }).click();
  await page.getByLabel("Justificación obligatoria").fill("Aceptación registrada solo para demostrar la trazabilidad");
  await page.getByRole("button", { name: /registrar aceptación/i }).click();
  await expect(page.getByText(/riesgo aceptado/i)).toBeVisible();

  await expect(page.locator(".react-pdf__Page canvas")).toBeVisible();
  await expect(page.getByRole("link", { name: /prorrateo master completado/i })).toHaveAttribute("href", /reconciliation\.xlsx/);
  await expect(page.getByRole("link", { name: /3 din pdf/i })).toHaveAttribute("href", /din\.pdf/);
  if (screenshotRoot) await page.screenshot({ path: path.join(screenshotRoot, "review-desktop.png"), fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("heading", { name: "700612", exact: true })).toBeVisible();
  if (screenshotRoot) await page.screenshot({ path: path.join(screenshotRoot, "review-mobile.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("expediente incompleto muestra faltantes y controles pendientes", async ({ page }) => {
  await page.goto("/");
  const instruction = path.join(fixtureRoot, "scenario_A_clean", "00_INSTRUCCION_DESPACHO_700611.pdf");
  await page.locator('input[type="file"]').nth(1).setInputFiles(instruction);
  await expect(page.getByRole("heading", { name: "700611", exact: true })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText("Expediente incompleto")).toBeVisible();
  await expect(page.getByText("1 de 8 archivos requeridos")).toBeVisible();
  await expect(page.getByText("7 faltantes")).toBeVisible();
  await expect(page.getByText("12 controles provisionales pendientes por documentos faltantes")).toBeVisible();
  await expect(page.getByText("Cálculo pendiente: agregue los documentos comerciales faltantes.")).toBeVisible();
  await expect(page.getByText(/NaN/)).toHaveCount(0);
  await expect(page.locator(".react-pdf__Page canvas")).toBeVisible();
  if (screenshotRoot) await page.screenshot({ path: path.join(screenshotRoot, "review-incomplete.png"), fullPage: true });
});

test("escenario de 40 facturas pagina la vista y genera 40 DIN", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /escenario c/i }).click();
  await expect(page.getByRole("heading", { name: "700613", exact: true })).toBeVisible({ timeout: 240_000 });
  await expect(page.getByText("Líneas 1–20 de 40")).toBeVisible();
  await expect(page.getByRole("link", { name: /40 din json/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /40 din pdf/i })).toBeVisible();
  await page.getByRole("button", { name: "Página siguiente" }).click();
  await expect(page.getByText("Líneas 21–40 de 40")).toBeVisible();
  await expect(page.getByRole("table").getByText("BN26010640", { exact: true })).toBeVisible();
});
