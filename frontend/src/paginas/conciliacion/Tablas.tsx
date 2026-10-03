import clsx from 'clsx'
import type { ReactNode } from 'react'

import type { Movimiento, Partida, TipoCruce } from '../../api/tipos'
import { Insignia, type Tono } from '../../componentes/ui/Insignia'
import { pesos } from '../../lib/formato'

export type Cabecera = string | { texto: string; derecha: true }

export function Tabla({ cabeceras, children }: { cabeceras: Cabecera[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs font-medium tracking-wide text-slate-500 uppercase">
          <tr>
            {cabeceras.map((c, i) => (
              <th
                key={i}
                className={clsx('px-4 py-2.5 whitespace-nowrap', typeof c !== 'string' && 'text-right')}
              >
                {typeof c === 'string' ? c : c.texto}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  )
}

export function Celda({
  children,
  derecha = false,
  className,
}: {
  children: ReactNode
  derecha?: boolean
  className?: string
}) {
  return (
    <td className={clsx('px-4 py-2.5 align-top', derecha && 'monto text-right', className)}>{children}</td>
  )
}

export function OrigenPartida({ p }: { p: Partida }) {
  return p.origen === 'arrastre' ? <Insignia tono="violeta">Mes anterior</Insignia> : null
}

export function DescripcionPartida({ p }: { p: Partida }) {
  if (p.tipo === 'INGRESO') {
    return (
      <span>
        {p.depto ? `Depto ${p.depto}` : 'Ingreso'}
        {p.glosa && <span className="text-slate-500"> · {p.glosa}</span>}
      </span>
    )
  }
  return <span className="line-clamp-2" title={p.glosa}>{p.glosa || 'Egreso'}</span>
}

export function DescripcionMovimiento({ m }: { m: Movimiento }) {
  return (
    <span>
      <span className="line-clamp-2" title={m.descripcion}>
        {m.descripcion || (m.es_cargo ? 'Cargo' : 'Abono')}
      </span>
      {m.documento && <span className="text-xs text-slate-500">Doc. {m.documento}</span>}
    </span>
  )
}

export function MontoMovimiento({ m }: { m: Movimiento }) {
  return (
    <span className={m.es_cargo ? 'text-rose-700' : 'text-emerald-700'}>
      {m.es_cargo ? '−' : '+'}
      {pesos(m.monto)}
    </span>
  )
}

const TIPOS_CRUCE: Record<TipoCruce, { texto: string; tono: Tono }> = {
  cheque: { texto: 'Nº de cheque', tono: 'marca' },
  monto_fecha: { texto: 'Monto y fecha', tono: 'cielo' },
  sugerido: { texto: 'Sugerido', tono: 'ambar' },
  manual: { texto: 'Manual', tono: 'violeta' },
}

export function InsigniaTipoCruce({ tipo }: { tipo: TipoCruce }) {
  const { texto, tono } = TIPOS_CRUCE[tipo]
  return <Insignia tono={tono}>{texto}</Insignia>
}
