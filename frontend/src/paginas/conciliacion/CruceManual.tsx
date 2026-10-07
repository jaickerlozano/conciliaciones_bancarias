import clsx from 'clsx'
import { ArrowRightLeft } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { useAccionConciliacion } from '../../api/consultas'
import type { Conciliacion, Movimiento, Partida } from '../../api/tipos'
import { Boton } from '../../componentes/ui/Boton'
import { Vacio } from '../../componentes/ui/Estados'
import { Insignia } from '../../componentes/ui/Insignia'
import { Modal } from '../../componentes/ui/Modal'
import { fecha, pesos } from '../../lib/formato'
import { DescripcionMovimiento, DescripcionPartida } from './Tablas'

export type OrigenCruce = { partida: Partida } | { movimiento: Movimiento }

/** Cruce manual. Desde una partida pendiente: elige un movimiento libre del mismo monto (1:1).
 * Desde un movimiento libre: elige una o varias partidas pendientes cuya suma sea su monto
 * (cruce agrupado). Sentido compatible: egreso↔cargo, ingreso↔abono. */
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

  const cruzar = (partidas: number[], movimiento: number) =>
    cruzarManual.mutate(
      { partidas, movimiento },
      {
        onSuccess: () => {
          toast.success(
            partidas.length > 1
              ? `Cruce agrupado registrado (${partidas.length} partidas)`
              : 'Cruce manual registrado',
          )
          alCerrar()
        },
        onError: (e) => toast.error(e.message),
      },
    )

  if (origen && 'movimiento' in origen) {
    // `key` reinicia la selección al cambiar de movimiento
    return (
      <DesdeMovimiento
        key={origen.movimiento.id}
        c={c}
        m={origen.movimiento}
        alCerrar={alCerrar}
        cargando={cruzarManual.isPending}
        alCruzar={cruzar}
      />
    )
  }

  let contenido = null
  if (origen) {
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
            alElegir: () => cruzar([p.id], m.id),
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

/** Días entre dos fechas ISO (sin fecha: al final de la lista). */
function distanciaDias(a: string | null, b: string): number {
  if (!a) return Number.POSITIVE_INFINITY
  return Math.abs(Date.parse(a) - Date.parse(b)) / 86_400_000
}

function DesdeMovimiento({
  c,
  m,
  alCerrar,
  cargando,
  alCruzar,
}: {
  c: Conciliacion
  m: Movimiento
  alCerrar: () => void
  cargando: boolean
  alCruzar: (partidas: number[], movimiento: number) => void
}) {
  const [elegidas, setElegidas] = useState<Set<number>>(() => new Set())

  // compatibles de monto ≤ al movimiento: primero las de monto exacto, luego por cercanía de fecha
  const candidatos = useMemo(
    () =>
      (m.es_cargo ? c.cheques_pendientes : c.depositos_pendientes)
        .filter((p) => p.monto > 0 && p.monto <= m.monto)
        .map((p) => ({ p, exacto: p.monto === m.monto, dias: distanciaDias(p.fecha, m.fecha) }))
        .sort((a, b) => Number(b.exacto) - Number(a.exacto) || a.dias - b.dias),
    [c, m],
  )

  const seleccion = candidatos.filter(({ p }) => elegidas.has(p.id)).map(({ p }) => p)
  const suma = seleccion.reduce((t, p) => t + p.monto, 0)
  const resto = m.monto - suma
  const cuadra = seleccion.length > 0 && resto === 0

  const alternar = (id: number) =>
    setElegidas((previas) => {
      const nuevas = new Set(previas)
      if (nuevas.has(id)) nuevas.delete(id)
      else nuevas.add(id)
      return nuevas
    })

  const tipoPartidas = m.es_cargo ? 'egresos' : 'ingresos'
  const pie =
    candidatos.length === 0 ? undefined : (
      <div className="flex w-full flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-700" aria-live="polite">
          <span className="monto">
            Seleccionado {pesos(suma)} de {pesos(m.monto)}
          </span>
          <span className="mx-2 text-slate-300">·</span>
          <strong
            className={clsx('monto', cuadra ? 'text-emerald-700' : resto < 0 ? 'text-rose-700' : 'text-amber-700')}
          >
            {cuadra ? 'Cuadra' : resto < 0 ? `Sobran ${pesos(-resto)}` : `Faltan ${pesos(resto)}`}
          </strong>
        </p>
        <Boton
          icono={ArrowRightLeft}
          disabled={!cuadra}
          cargando={cargando}
          onClick={() => alCruzar(seleccion.map((p) => p.id), m.id)}
          aria-label="Cruzar seleccionadas"
        >
          Cruzar{seleccion.length > 1 ? ` (${seleccion.length})` : ''}
        </Boton>
      </div>
    )

  return (
    <Modal
      abierto
      alCerrar={alCerrar}
      ancho="lg"
      titulo="Cruzar manualmente"
      descripcion={`Elija uno o varios ${tipoPartidas} pendientes cuya suma sea igual al monto del movimiento.`}
      pie={pie}
    >
      <Origen titulo={m.es_cargo ? 'Cargo del banco' : 'Abono del banco'}>
        {fecha(m.fecha)} · <DescripcionMovimiento m={m} /> ·{' '}
        <strong className="monto">{pesos(m.monto)}</strong>
      </Origen>
      {candidatos.length === 0 ? (
        <Vacio icono={ArrowRightLeft} titulo="Sin candidatos">
          No hay {tipoPartidas} pendientes por {pesos(m.monto)} o menos. Si falta en la planilla,
          regístrelo allí y vuelva a subirla.
        </Vacio>
      ) : (
        <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
          {candidatos.map(({ p, exacto }) => {
            const id = `cruce-partida-${p.id}`
            return (
              <li
                key={p.id}
                className={clsx(
                  'flex items-center gap-3 px-4 py-3 text-sm',
                  exacto && 'bg-emerald-50/60',
                  elegidas.has(p.id) && 'bg-marca-50',
                )}
              >
                <input
                  id={id}
                  type="checkbox"
                  checked={elegidas.has(p.id)}
                  onChange={() => alternar(p.id)}
                  className="size-4 shrink-0 rounded border-slate-300 text-marca-700 focus:ring-marca-600"
                />
                <label htmlFor={id} className="min-w-0 flex-1 cursor-pointer text-slate-700">
                  <span className="font-medium">#{p.comprobante ?? '—'}</span> · {fecha(p.fecha)} ·{' '}
                  <DescripcionPartida p={p} />
                  <span className="sr-only"> por {pesos(p.monto)}</span>
                </label>
                {exacto && <Insignia tono="verde">Monto exacto</Insignia>}
                <strong className="monto shrink-0">{pesos(p.monto)}</strong>
                {exacto && (
                  <Boton
                    tamano="sm"
                    variante="secundario"
                    icono={ArrowRightLeft}
                    cargando={cargando}
                    onClick={() => alCruzar([p.id], m.id)}
                  >
                    Cruzar
                  </Boton>
                )}
              </li>
            )
          })}
        </ul>
      )}
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
