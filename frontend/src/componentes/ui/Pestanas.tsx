import clsx from 'clsx'

export interface Pestana<T extends string> {
  id: T
  etiqueta: string
  cantidad?: number
  resaltar?: boolean
}

export function Pestanas<T extends string>({
  pestanas,
  activa,
  alCambiar,
}: {
  pestanas: Pestana<T>[]
  activa: T
  alCambiar: (id: T) => void
}) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-200 px-2">
      {pestanas.map((p) => (
        <button
          key={p.id}
          type="button"
          role="tab"
          aria-selected={p.id === activa}
          onClick={() => alCambiar(p.id)}
          className={clsx(
            '-mb-px flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
            p.id === activa
              ? 'border-marca-600 text-marca-800'
              : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
          )}
        >
          {p.etiqueta}
          {p.cantidad !== undefined && (
            <span
              className={clsx(
                'monto rounded-full px-1.5 py-px text-xs',
                p.resaltar && p.cantidad > 0
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-slate-100 text-slate-600',
              )}
            >
              {p.cantidad}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
