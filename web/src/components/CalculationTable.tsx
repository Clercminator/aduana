import { Calculator, ChevronLeft, ChevronRight, CircleDollarSign } from "lucide-react";
import { useState } from "react";
import type { DispatchState } from "../types";

const PAGE_SIZE = 20;
function formatAmount(value: unknown, formatter: Intl.NumberFormat): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? formatter.format(amount) : "—";
}

export function CalculationTable({ calculation }: { calculation: NonNullable<DispatchState["calculation"]> }) {
  const [page, setPage] = useState(1);
  const totals = calculation.totals;
  const sourceCurrency = String(totals.currency || "");
  const settlementCurrency = String(totals.settlement_currency || "");
  const sourceFormatter = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const settlementFormatter = new Intl.NumberFormat("es-CL", { minimumFractionDigits: settlementCurrency === "CLP" ? 0 : 2, maximumFractionDigits: settlementCurrency === "CLP" ? 0 : 2 });
  const levyLabels = calculation.lines[0]?.levies.map((levy) => `${levy.label}${levy.recoverable ? " (recuperable)" : ""}`) || [];
  const pageCount = Math.max(1, Math.ceil(calculation.lines.length / PAGE_SIZE));
  const visiblePage = Math.min(page, pageCount);
  const pageStart = (visiblePage - 1) * PAGE_SIZE;
  const visibleLines = calculation.lines.slice(pageStart, pageStart + PAGE_SIZE);

  return (
    <section className="calculation-section">
      <div className="calculation-head">
        <div><span className="kicker"><Calculator size={14} /> Prorrateo y tributos</span><h2>Resultado según documentos</h2></div>
        <div className="total-cards">
          <div><span>Declaración · valor aduanero</span><strong>{sourceCurrency} {formatAmount(totals.customs_value, sourceFormatter)}</strong></div>
          <div><span>Declaración · pago</span><strong>{sourceCurrency} {formatAmount(totals.total_payable, sourceFormatter)}</strong></div>
          <div><span>Costo · sin tributos recuperables</span><strong>{sourceCurrency} {formatAmount(totals.landed_cost, sourceFormatter)}</strong></div>
          <div className="primary-total"><span>Pago estimado</span><strong>{settlementCurrency} {formatAmount(totals.total_payable_settlement, settlementFormatter)}</strong></div>
        </div>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Factura / HS</th><th>FOB</th><th>Flete</th><th>Seguro</th><th>Valor aduanero</th>{levyLabels.map((label) => <th key={label}>{label}</th>)}<th>Total tributos</th><th>Costo puesto</th></tr></thead>
          <tbody>{calculation.lines.length === 0 ? <tr><td className="empty-calculation" colSpan={levyLabels.length + 7}>Cálculo pendiente: agregue los documentos comerciales faltantes.</td></tr> : visibleLines.map((line, index) => {
            return <tr key={`${line.invoice}-${line.hs_code}-${pageStart + index}`}><td><strong>{line.invoice}</strong><span>{line.hs_code} · {line.duty_reason}</span></td><td>{sourceFormatter.format(Number(line.fob))}</td><td>{sourceFormatter.format(Number(line.allocations.freight))}</td><td>{sourceFormatter.format(Number(line.allocations.insurance))}{line.residual_codes.length > 0 && <small className="adjustment">ajuste</small>}</td><td>{sourceFormatter.format(Number(line.customs_value))}</td>{line.levies.map((levy) => <td key={levy.code}>{sourceFormatter.format(Number(levy.amount.amount))}{levy.code === line.levies[0]?.code ? <span>{Number(line.duty_rate) * 100}%</span> : null}</td>)}<td><strong>{sourceFormatter.format(Number(line.levy_total))}</strong></td><td><strong>{sourceFormatter.format(Number(line.landed_cost))}</strong></td></tr>;
          })}</tbody>
        </table>
      </div>
      {calculation.lines.length > PAGE_SIZE ? <nav className="table-pagination" aria-label="Paginación de líneas"><span>Líneas {pageStart + 1}–{Math.min(pageStart + PAGE_SIZE, calculation.lines.length)} de {calculation.lines.length}</span><div><button type="button" aria-label="Página anterior" disabled={visiblePage === 1} onClick={() => setPage((current) => Math.max(1, Math.min(current, pageCount) - 1))}><ChevronLeft size={15} /></button><strong>Página {visiblePage} de {pageCount}</strong><button type="button" aria-label="Página siguiente" disabled={visiblePage === pageCount} onClick={() => setPage((current) => Math.min(pageCount, current + 1))}><ChevronRight size={15} /></button></div></nav> : null}
      <footer className="calc-footer"><span><CircleDollarSign size={15} /> Tipo de cambio aduanero {totals.fx_period} · {totals.fx_rate} · {totals.fx_source}</span><strong>Las reglas fiscales y el mapeo de declaración son provisionales.</strong></footer>
    </section>
  );
}
