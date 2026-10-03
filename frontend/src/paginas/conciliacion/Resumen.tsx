import clsx from 'clsx'
import { AlertTriangle, CheckCircle2, Pencil } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'

import { useAccionConciliacion } from '../../api/consultas'
import type { Conciliacion } from '../../api/tipos'
import { Boton } from '../../componentes/ui/Boton'
import { Tarjeta } from '../../componentes/ui/Tarjeta'
import { leerMonto, nombrePeriodo, periodoAnterior, pesos } from '../../lib/formato'

function Linea({
  etiqueta,
  monto,
  signo,
  fuerte = false,
  extra,
}: {
  etiqueta: ReactNode
  monto: number | null
  signo?: '+' | '−'
  fuerte?: boolean
  extra?: ReactNode
}) {
  return (
    <div
      className={clsx(
        'flex items-center justify-between gap-4 py-2 text-sm',
        fuerte ? 'font-semibold text-slate-900' : 'text-slate-600',
      )}
    >
      <span className="flex items-center gap-2">
        <span className="w-3 text-slate-400">{signo}</span>
        {etiqueta}
        {extra}
      </span>
      <span className="monto">{pesos(monto)}</span>
    </div>
  )
}

/** El cálculo de la conciliación, con la misma estructura de la planilla del cliente. */
export function Resumen({ c }: { c: Conciliacion }) {
  const r = c.resumen
  const importada = c.estado === 'importada'
  const cuadra = r.diferencia === 0

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <Tarjeta titulo="Cálculo de la conciliación" className="lg:col-span-2">
        {importada ? (
          <Linea etiqueta="Saldo según registro (importado)" monto={r.saldo_registro} fuerte />
        ) : (
          <div className="divide-y divide-slate-100">
            <Linea
              etiqueta={`Saldo conciliado ${nombrePeriodo(periodoAnterior(c.periodo))}`}
              monto={r.saldo_anterior}
            />
            <Linea etiqueta={`Ingresos de ${nombrePeriodo(c.periodo)}`} monto={r.total_ingresos} signo="+" />
            <Linea etiqueta={`Egresos de ${nombrePeriodo(c.periodo)}`} monto={r.total_egresos} signo="−" />
            <Linea
              etiqueta="Redondeo"
              monto={r.redondeo}
              signo="+"
              extra={c.estado === 'procesada' && <EditarRedondeo c={c} />}
            />
            <Linea etiqueta="Saldo según registro" monto={r.saldo_registro} fuerte />
          </div>
        )}
        <div className="mt-2 divide-y divide-slate-100 border-t-2 border-slate-200">
          <Linea etiqueta="Cheques girados no cobrados" monto={r.total_cheques_pendientes} signo="+" />
          <Linea
            etiqueta="Depósitos contabilizados no registrados en banco"
            monto={r.total_depositos_pendientes}
            signo="−"
          />
          <Linea etiqueta="Movimientos no contabilizados" monto={r.total_no_contabilizados} signo="+" />
          <Linea etiqueta="Saldo según conciliación" monto={r.saldo_conciliacion} fuerte />
          <Linea etiqueta="Saldo según banco" monto={r.saldo_banco} fuerte />
        </div>
      </Tarjeta>

      <div
        className={clsx(
          'flex flex-col justify-between rounded-xl border p-6 shadow-sm',
          cuadra ? 'border-emerald-200 bg-emerald-50' : 'border-rose-200 bg-rose-50',
        )}
      >
        <div className="flex items-center gap-2">
          {cuadra ? (
            <CheckCircle2 className="size-6 text-emerald-600" aria-hidden />
          ) : (
            <AlertTriangle className="size-6 text-rose-600" aria-hidden />
          )}
          <span className={clsx('text-sm font-semibold', cuadra ? 'text-emerald-900' : 'text-rose-900')}>
            {cuadra ? 'La conciliación cuadra' : 'Hay diferencia'}
          </span>
        </div>
        <p className={clsx('monto mt-4 text-4xl font-semibold tracking-tight', cuadra ? 'text-emerald-800' : 'text-rose-800')}>
          {pesos(r.diferencia)}
        </p>
        <p className="mt-1 text-xs text-slate-600">Diferencia = saldo banco − saldo según conciliación</p>
        {!importada && c.estado !== 'cerrada' && (
          <p className="mt-6 text-sm text-slate-700">
            {r.cruces_por_revisar > 0
              ? `Quedan ${r.cruces_por_revisar} cruces por revisar antes de cerrar.`
              : cuadra
                ? 'Todo revisado: puede cerrar el mes.'
                : 'Busque la diferencia en los pendientes y movimientos no contabilizados.'}
          </p>
        )}
      </div>
    </div>
  )
}

function EditarRedondeo({ c }: { c: Conciliacion }) {
  const { redondeo } = useAccionConciliacion(c.id)
  const [editando, setEditando] = useState(false)
  const [valor, setValor] = useState(String(c.resumen.redondeo))

  if (!editando) {
    return (
      <button
        type="button"
        onClick={() => setEditando(true)}
        className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-marca-700"
        title="Ajustar redondeo (decimales de cuotas en UF, máx. $100)"
        aria-label="Ajustar redondeo"
      >
        <Pencil className="size-3.5" />
      </button>
    )
  }
  const monto = leerMonto(valor)
  return (
    <span className="flex items-center gap-1.5">
      <input
        autoFocus
        value={valor}
        onChange={(e) => setValor(e.target.value)}
        className="monto w-20 rounded-md px-2 py-0.5 text-right text-sm ring-1 ring-slate-300 focus:ring-2 focus:ring-marca-600 focus:outline-none"
        aria-label="Redondeo"
      />
      <Boton
        tamano="sm"
        disabled={monto === null}
        cargando={redondeo.isPending}
        onClick={() =>
          monto !== null &&
          redondeo.mutate(monto, {
            onSuccess: () => {
              toast.success('Redondeo actualizado')
              setEditando(false)
            },
            onError: (e) => toast.error(e.message),
          })
        }
      >
        Aplicar
      </Boton>
      <Boton tamano="sm" variante="fantasma" onClick={() => setEditando(false)}>
        Cancelar
      </Boton>
    </span>
  )
}
