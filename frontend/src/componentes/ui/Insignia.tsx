import clsx from 'clsx'
import type { ReactNode } from 'react'

import type { EstadoConciliacion } from '../../api/tipos'

export type Tono = 'gris' | 'marca' | 'verde' | 'ambar' | 'rojo' | 'cielo' | 'violeta'

const TONOS: Record<Tono, string> = {
  gris: 'bg-slate-100 text-slate-700 ring-slate-500/20',
  marca: 'bg-marca-50 text-marca-800 ring-marca-600/20',
  verde: 'bg-emerald-50 text-emerald-800 ring-emerald-600/20',
  ambar: 'bg-amber-50 text-amber-800 ring-amber-600/25',
  rojo: 'bg-rose-50 text-rose-800 ring-rose-600/20',
  cielo: 'bg-sky-50 text-sky-800 ring-sky-600/20',
  violeta: 'bg-violet-50 text-violet-800 ring-violet-600/20',
}

export function Insignia({ tono = 'gris', children }: { tono?: Tono; children: ReactNode }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset',
        TONOS[tono],
      )}
    >
      {children}
    </span>
  )
}

const ESTADOS: Record<EstadoConciliacion, { texto: string; tono: Tono }> = {
  importada: { texto: 'Saldo inicial', tono: 'violeta' },
  borrador: { texto: 'Borrador', tono: 'gris' },
  procesada: { texto: 'En revisión', tono: 'cielo' },
  cerrada: { texto: 'Cerrada', tono: 'verde' },
}

export function InsigniaEstado({ estado }: { estado: EstadoConciliacion }) {
  const { texto, tono } = ESTADOS[estado]
  return <Insignia tono={tono}>{texto}</Insignia>
}
