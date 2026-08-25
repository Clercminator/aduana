import { expect, test } from "@playwright/test";
import path from "node:path";

const lines = Array.from({ length: 40 }, (_, index) => ({
  invoice: `BN260106${String(index + 1).padStart(2, "0")}`,
  description: `Producto sintético ${index + 1}`,
  hs_code: "9405.20",
  fob: "1000.00",
  share: "0.025",
  allocations: { freight: "25.00", insurance: "0.55" },
  residual_codes: [],
  customs_value: "1025.55",
  duty_rate: "0.00",
  duty_reason: "Preferencia aplicada",
  levy_total: "194.85",
  landed_cost: "1025.55",
  declaration_view: { payable_levies: "194.85" },
  cost_view: {
    capitalized_levies: "0.00",
    recoverable_levies_excluded: "194.85",
    landed_cost: "1025.55",
  },
  levies: [
    {
      code: "AD_VALOREM",
      label: "Derecho ad valorem",
      base_expression: "customs_value",
      rate: "0.00",
      amount: { amount: "0.00", currency: "USD" },
      recoverable: false,
    },
    {
      code: "IVA",
      label: "Impuesto al Valor Agregado",
      base_expression: "customs_value + AD_VALOREM",
      rate: "0.19",
      amount: { amount: "194.85", currency: "USD" },
      recoverable: true,
    },
  ],
}));
lines.push({ ...lines[0], description: "Segunda línea de la primera factura" });

const state = {
  dispatch: {
    id: "dispatch-volume",
    despacho_no: "700613",
    referencia: "54415CLFA/26J28-9",
    status: "review",
    regime: "import_for_consumption",
    jurisdiction: "CL",
    jurisdiction_config_hash: "c".repeat(64),
    client_config_hash: "e".repeat(64),
    client: "FALABELLA_RETAIL",
    din_acceptance_date: "2026-08-18",
    fx_period: "2026-08",
    expected_documents: {
      bill_of_lading: 1,
      commercial_invoice: 40,
      packing_list: 1,
      insurance_certificate: 1,
      certificate_of_origin: 1,
    },
    created_at: "2026-08-24T12:00:00Z",
  },
  documents: [],
  calculation: {
    label: "según documentos, pendiente de revisión",
    rules: Array.from({ length: 12 }, (_, index) => ({
      id: index === 11 ? "EXC-12" : `CHK-${String(index + 1).padStart(2, "0")}`,
      severity: index === 11 ? "CRITICAL" : "INFO",
      status: "PASS",
      title: `Control ${index + 1}`,
      detail: "Conforme",
      source_refs: [],
    })),
    lines,
    totals: {
      currency: "USD",
      settlement_currency: "CLP",
      customs_value: "501336.22",
      total_payable: "95253.87",
      landed_cost: "501336.22",
      total_payable_settlement: "91772341",
      fx_rate: "963.45",
      fx_source: "dólar aduanero mensual ficticio del demo",
      fx_period: "2026-08",
    },
    scenarios: {},
  },
  calculation_run: null,
  audit: [],
  artifacts: [],
};

test("pagina líneas y cuenta una DIN por factura única", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  await page.route("**/api/demo/load/C", (route) =>
    route.fulfill({ json: { dispatch_id: "dispatch-volume", job_id: "job-volume", added: 45, duplicates: 0 } }),
  );
  await page.route("**/api/jobs/job-volume", (route) =>
    route.fulfill({
      json: {
        id: "job-volume",
        dispatch_id: "dispatch-volume",
        status: "done",
        stage: "done",
        progress: "1",
        error: null,
        elapsed_seconds: 12.4,
      },
    }),
  );
  await page.route("**/api/dispatches/dispatch-volume", (route) => route.fulfill({ json: state }));

  await page.goto("/");
  await expect(page).toHaveTitle(/Control Aduanero/i);
  await expect(page.getByRole("heading", { name: /documentos dispersos/i })).toBeVisible();
  await page.getByRole("button", { name: /escenario c/i }).click();
  await expect(page.getByRole("heading", { name: "700613", exact: true })).toBeVisible();
  await expect(page.getByText("Líneas 1–20 de 41")).toBeVisible();
  await expect(page.getByRole("link", { name: /40 din json/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /40 din pdf/i })).toBeVisible();
  await page.getByRole("button", { name: "Página siguiente" }).click();
  await expect(page.getByText("Líneas 21–40 de 41")).toBeVisible();
  await expect(page.getByText("BN26010640", { exact: true })).toBeVisible();
  expect(consoleErrors).toEqual([]);

  const screenshotRoot = process.env.QA_SCREENSHOT_DIR;
  if (screenshotRoot) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshotRoot, "pagination-desktop.png") });
    await page.locator(".table-pagination").screenshot({ path: path.join(screenshotRoot, "pagination-controls-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByText("Líneas 21–40 de 41")).toBeVisible();
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(screenshotRoot, "pagination-mobile.png") });
    await page.locator(".table-pagination").screenshot({ path: path.join(screenshotRoot, "pagination-controls-mobile.png") });
  }
});
