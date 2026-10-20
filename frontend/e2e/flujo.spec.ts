import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { parseCsv, readZip } from "./zip";

function must<T>(value: T | undefined, what: string): T {
  if (value === undefined) throw new Error(`falta ${what}`);
  return value;
}

// Quickstart, escenario 6: seleccionar fecha y periodo, ejecutar, ver tablas y topología,
// cambiar el coloreado y descargar el zip. Requiere el snapshot incluido (2026-10-20).

test("flujo completo desde la interfaz", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("label")).toContainText("Flujo sobre despacho programado");
  await expect(page.locator("footer")).toContainText("XM S.A. E.S.P.");

  await page.getByTestId("snapshot-date").selectOption("2026-10-20");
  await page.getByTestId("period").fill("19");
  await page.getByTestId("run-button").click();

  await expect(page.getByTestId("case-quality")).toBeVisible({ timeout: 90_000 });
  await expect(page.getByTestId("results")).toContainText("Estado: convergio", { timeout: 90_000 });
  await expect(page.getByTestId("table-buses")).toBeVisible();
  await page.getByRole("button", { name: "Transformadores" }).click();
  await expect(page.getByTestId("table-branches")).toBeVisible();
  await page.getByTestId("only-violations").check();

  await expect(page.getByTestId("topology")).toBeVisible();
  await page.getByTestId("color-by").selectOption("loading");
  await expect(page.locator(".legend")).toContainText("100 %");

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-link").click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/\.zip$/);
  const path = await download.path();
  expect(path).not.toBeNull();

  // El zip coincide valor a valor con GET /api/runs/{id} (quickstart escenario 6, SC-007).
  const href = await page.getByTestId("export-link").getAttribute("href");
  const runId = /\/api\/runs\/([^/]+)\/export/.exec(href ?? "")?.[1];
  expect(runId).toBeTruthy();
  const run = (await (await page.request.get(`/api/runs/${runId}`)).json()) as {
    run_id: string;
    case_id: string;
    result: {
      buses: { bus_id: string; vm_pu: number; va_degree: number }[];
      lines: { element_id: string; loading_percent: number }[];
      trafos: { element_id: string }[];
      generators: { gen_id: string; p_mw: number }[];
    };
  };
  const files = readZip(readFileSync(path as string));
  expect([...files.keys()].sort()).toEqual(
    ["barras.csv", "generadores.csv", "lineas.csv", "metadatos.json", "transformadores.csv"].sort(),
  );
  const meta = JSON.parse(must(files.get("metadatos.json"), "metadatos.json").toString("utf8")) as Record<string, unknown>;
  expect(meta.case_id).toBe(run.case_id);
  const trace = meta.trace as { case_id: string; period: number; flow_type: string; pandapower_version: string };
  expect(trace.case_id).toBe(run.case_id);
  expect(trace.period).toBe(19);
  expect(trace.flow_type).toBe("ac");
  expect(trace.pandapower_version).toBe("3.5.6");
  expect(JSON.stringify(meta)).toContain("XM S.A. E.S.P.");

  const buses = parseCsv(must(files.get("barras.csv"), "barras.csv").toString("utf8"));
  expect(buses).toHaveLength(run.result.buses.length);
  const byBus = new Map(run.result.buses.map((b) => [b.bus_id, b]));
  for (const row of buses) {
    const b = must(byBus.get(row.bus_id), row.bus_id);
    expect(Number(row.vm_pu)).toBeCloseTo(b.vm_pu, 9);
    expect(Number(row.va_degree)).toBeCloseTo(b.va_degree, 9);
  }
  const lines = parseCsv(must(files.get("lineas.csv"), "lineas.csv").toString("utf8"));
  expect(lines).toHaveLength(run.result.lines.length);
  const byLine = new Map(run.result.lines.map((l) => [l.element_id, l]));
  for (const row of lines) {
    expect(Number(row.loading_percent)).toBeCloseTo(must(byLine.get(row.element_id), row.element_id).loading_percent, 9);
  }
  expect(parseCsv(must(files.get("transformadores.csv"), "transformadores.csv").toString("utf8"))).toHaveLength(run.result.trafos.length);
  const gens = parseCsv(must(files.get("generadores.csv"), "generadores.csv").toString("utf8"));
  expect(gens).toHaveLength(run.result.generators.length);
  const byGen = new Map(run.result.generators.map((g) => [g.gen_id, g]));
  for (const row of gens) {
    expect(Number(row.p_mw)).toBeCloseTo(must(byGen.get(row.gen_id), row.gen_id).p_mw, 9);
  }
});

test("un periodo inválido se rechaza con un mensaje claro", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("period").fill("25");
  await expect(page.getByText("El periodo debe estar entre 1 y 24.")).toBeVisible();
  await expect(page.getByTestId("run-button")).toBeDisabled();
});
