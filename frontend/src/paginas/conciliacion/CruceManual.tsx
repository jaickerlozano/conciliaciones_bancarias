import { ArrowRightLeft } from 'lucide-react'
import { toast } from 'sonner'

import { useAccionConciliacion } from '../../api/consultas'
import type { Conciliacion, Movimiento, Partida } from '../../api/tipos'
import { Boton } from '../../componentes/ui/Boton'
import { Vacio } from '../../componentes/ui/Estados'
import { Modal } from '../../componentes/ui/Modal'
import { fecha, pesos } from '../../lib/formato'
import { DescripcionMovimiento, DescripcionPartida } from './Tablas'

export type OrigenCruce = { partida: Partida } | { movimiento: Movimiento }

/** Cruce manual: desde una partida pendiente elige un movimiento libre (o al revés),
 * siempre del mismo monto y sentido compatible (egreso↔cargo, ingreso↔abono). */
export function CruceManual({
  c,
  origen,
  alCerrar,
}: {
  c: Conciliacion
  origen: OrigenCruce | null
  alCerrar: () => void
}) {
  const { cruzarManual } = useAccionConciliacion(c.id)

  const cruzar = (partida: number, movimiento: number) =>
    cruzarManual.mutate(
      { partida, movimiento },
      {
        onSuccess: () => {
          toast.success('Cruce manual registrado')
          alCerrar()
        },
        onError: (e) => toast.error(e.message),
      },
    )

  let contenido = null
  if (origen && 'partida' in origen) {
    const p = origen.partida
    const candidatos = c.movimientos_no_contabilizados.filter(
      (m) => m.monto === p.monto && m.es_cargo === (p.tipo === 'EGRESO'),
    )
    contenido = (
      <>
        <Origen titulo={p.tipo === 'EGRESO' ? 'Egreso del libro' : 'Ingreso del libro'}>
          <span className="font-medium">#{p.comprobante ?? '—'}</span> · {fecha(p.fecha)} ·{' '}
          <DescripcionPartida p={p} /> · <strong className="monto">{pesos(p.monto)}</strong>
        </Origen>
        <Lista
          vacio={`No hay ${p.tipo === 'EGRESO' ? 'cargos' : 'abonos'} del banco sin cruzar por ${pesos(p.monto)}.`}
          items={candidatos.map((m) => ({
            clave: m.id,
            contenido: (
              <>
                {fecha(m.fecha)} · <DescripcionMovimiento m={m} />
              </>
            ),
            alElegir: () => cruzar(p.id, m.id),
          }))}
          cargando={cruzarManual.isPending}
        />
      </>
    )
  } else if (origen) {
    const m = origen.movimiento
    const candidatos = (m.es_cargo ? c.cheques_pendientes : c.depositos_pendientes).filter(
      (p) => p.monto === m.monto,
    )
    contenido = (
      <>
        <Origen titulo={m.es_cargo ? 'Cargo del banco' : 'Abono del banco'}>
          {fecha(m.fecha)} · <DescripcionMovimiento m={m} /> ·{' '}
          <strong className="monto">{pesos(m.monto)}</strong>
        </Origen>
        <Lista
          vacio={`No hay ${m.es_cargo ? 'egresos' : 'ingresos'} pendientes por ${pesos(m.monto)}. Si falta en la planilla, regístrelo allí y vuelva a subirla.`}
          items={candidatos.map((p) => ({
            clave: p.id,
            contenido: (
              <>
                <span className="font-medium">#{p.comprobante ?? '—'}</span> · {fecha(p.fecha)} ·{' '}
                <DescripcionPartida p={p} />
              </>
            ),
            alElegir: () => cruzar(p.id, m.id),
          }))}
          cargando={cruzarManual.isPending}
        />
      </>
    )
  }

  return (
    <Modal
      abierto={origen !== null}
      alCerrar={alCerrar}
      ancho="lg"
      titulo="Cruzar manualmente"
      descripcion="Solo se muestran los del mismo monto que aún no están cruzados."
    >
      {contenido}
    </Modal>
  )
}

function Origen({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <div className="mb-4 rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700 ring-1 ring-slate-200">
      <p className="mb-1 text-xs font-medium tracking-wide text-slate-500 uppercase">{titulo}</p>
      {children}
    </div>
  )
}

function Lista({
  items,
  vacio,
  cargando,
}: {
  items: { clave: number; contenido: React.ReactNode; alElegir: () => void }[]
  vacio: string
  cargando: boolean
}) {
  if (items.length === 0) return <Vacio icono={ArrowRightLeft} titulo="Sin candidatos">{vacio}</Vacio>
  return (
    <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
      {items.map((i) => (
        <li key={i.clave} className="flex items-center justify-between gap-4 px-4 py-3 text-sm">
          <span className="min-w-0 text-slate-700">{i.contenido}</span>
          <Boton tamano="sm" icono={ArrowRightLeft} cargando={cargando} onClick={i.alElegir}>
            Cruzar
          </Boton>
        </li>
      ))}
    </ul>
  )
}
