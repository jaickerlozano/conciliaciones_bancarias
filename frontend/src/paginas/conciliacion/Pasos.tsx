import clsx from 'clsx'
import { Check } from 'lucide-react'

import type { Conciliacion } from '../../api/tipos'

/** Indicador del flujo: 1 Archivos → 2 Revisión → 3 Cierre. */
export function Pasos({ c }: { c: Conciliacion }) {
  const tiposCargados = new Set(c.archivos.map((a) => a.tipo))
  const archivosListos = ['ingresos', 'egresos', 'cartola'].every((t) => tiposCargados.has(t as never))
  const pasos = [
    {
      titulo: 'Archivos',
      detalle: archivosListos ? 'Cargados' : `${tiposCargados.size} de 3 cargados`,
      hecho: c.estado !== 'borrador',
      actual: c.estado === 'borrador',
    },
    {
      titulo: 'Revisión',
      detalle:
        c.estado === 'borrador'
          ? 'Después de procesar'
          : c.resumen.cruces_por_revisar > 0
            ? `${c.resumen.cruces_por_revisar} cruces por revisar`
            : c.resumen.diferencia === 0
              ? 'Todo revisado'
              : 'Hay diferencia',
      hecho: c.estado === 'cerrada' || (c.estado === 'procesada' && c.resumen.cruces_por_revisar === 0 && c.resumen.diferencia === 0),
      actual: c.estado === 'procesada',
    },
    {
      titulo: 'Cierre',
      detalle: c.estado === 'cerrada' ? 'Mes cerrado' : 'Diferencia $0 y sin pendientes de revisión',
      hecho: c.estado === 'cerrada',
      actual: false,
    },
  ]

  return (
    <ol className="mb-6 grid gap-3 sm:grid-cols-3">
      {pasos.map((p, i) => (
        <li
          key={p.titulo}
          className={clsx(
            'flex items-center gap-3 rounded-xl border px-4 py-3',
            p.actual ? 'border-marca-300 bg-marca-50' : 'border-slate-200 bg-white',
          )}
        >
          <span
            className={clsx(
              'grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold',
              p.hecho
                ? 'bg-emerald-600 text-white'
                : p.actual
                  ? 'bg-marca-700 text-white'
                  : 'bg-slate-100 text-slate-500',
            )}
          >
            {p.hecho ? <Check className="size-4" /> : i + 1}
          </span>
          <span>
            <span className="block text-sm font-semibold text-slate-900">{p.titulo}</span>
            <span className="block text-xs text-slate-500">{p.detalle}</span>
          </span>
        </li>
      ))}
    </ol>
  )
}
