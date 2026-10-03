import { ArrowRightLeft, CheckCheck, CheckCircle2, History, Search, Undo2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { useAccionConciliacion } from '../../api/consultas'
import type { Conciliacion, Cruce, Movimiento, Partida } from '../../api/tipos'
import { Boton } from '../../componentes/ui/Boton'
import { Vacio } from '../../componentes/ui/Estados'
import { Insignia } from '../../componentes/ui/Insignia'
import { Pestanas, type Pestana } from '../../componentes/ui/Pestanas'
import { fecha, fechaHora, pesos } from '../../lib/formato'
import { CruceManual, type OrigenCruce } from './CruceManual'
import {
  Celda,
  DescripcionMovimiento,
  DescripcionPartida,
  InsigniaTipoCruce,
  MontoMovimiento,
  OrigenPartida,
  Tabla,
} from './Tablas'

type Id = 'revisar' | 'cheques' | 'depositos' | 'nocontab' | 'cruces' | 'avisos' | 'historial'

export function Revision({ c }: { c: Conciliacion }) {
  const porRevisar = c.cruces.filter((x) => x.requiere_revision)
  const editable = c.estado === 'procesada'
  const [activa, setActiva] = useState<Id>(
    c.estado === 'importada' ? 'cheques' : porRevisar.length ? 'revisar' : 'cheques',
  )
  const [origenCruce, setOrigenCruce] = useState<OrigenCruce | null>(null)
  // montos con contraparte libre: solo ahí tiene sentido ofrecer el cruce manual
  const cruzables = useMemo(() => {
    const clave = (monto: number, cargo: boolean) => `${cargo ? 'C' : 'A'}${monto}`
    const movs = new Set(c.movimientos_no_contabilizados.map((m) => clave(m.monto, m.es_cargo)))
    const partidas = new Set(
      [...c.cheques_pendientes, ...c.depositos_pendientes].map((p) => clave(p.monto, p.tipo === 'EGRESO')),
    )
    return {
      partida: (p: Partida) => editable && movs.has(clave(p.monto, p.tipo === 'EGRESO')),
      movimiento: (m: Movimiento) => editable && partidas.has(clave(m.monto, m.es_cargo)),
    }
  }, [c, editable])

  const pestanas: Pestana<Id>[] = [
    ...(c.estado === 'importada'
      ? []
      : [{ id: 'revisar' as const, etiqueta: 'Por revisar', cantidad: porRevisar.length, resaltar: true }]),
    { id: 'cheques', etiqueta: 'Cheques no cobrados', cantidad: c.cheques_pendientes.length },
    { id: 'depositos', etiqueta: 'Depósitos no en banco', cantidad: c.depositos_pendientes.length },
    { id: 'nocontab', etiqueta: 'No contabilizados', cantidad: c.movimientos_no_contabilizados.length },
    ...(c.estado === 'importada'
      ? []
      : [{ id: 'cruces' as const, etiqueta: 'Todos los cruces', cantidad: c.cruces.length }]),
    {
      id: 'avisos',
      etiqueta: 'Advertencias',
      cantidad: c.advertencias.length + (c.movimientos_repetidos.length ? 1 : 0),
      resaltar: true,
    },
    { id: 'historial', etiqueta: 'Historial' },
  ]

  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <Pestanas pestanas={pestanas} activa={activa} alCambiar={setActiva} />
      <div className="min-h-48">
        {activa === 'revisar' && <PorRevisar c={c} cruces={porRevisar} editable={editable} />}
        {activa === 'cheques' && (
          <TablaPartidas
            partidas={c.cheques_pendientes}
            vacio="Todos los cheques girados fueron cobrados."
            puedeCruzar={cruzables.partida}
            alCruzar={(partida) => setOrigenCruce({ partida })}
          />
        )}
        {activa === 'depositos' && (
          <TablaPartidas
            partidas={c.depositos_pendientes}
            vacio="Todos los ingresos registrados aparecen en el banco."
            puedeCruzar={cruzables.partida}
            alCruzar={(partida) => setOrigenCruce({ partida })}
          />
        )}
        {activa === 'nocontab' && (
          <TablaMovimientos
            movimientos={c.movimientos_no_contabilizados}
            puedeCruzar={cruzables.movimiento}
            alCruzar={(movimiento) => setOrigenCruce({ movimiento })}
          />
        )}
        {activa === 'cruces' && <TodosLosCruces c={c} editable={editable} />}
        {activa === 'avisos' && <Advertencias c={c} />}
        {activa === 'historial' && <Historial c={c} />}
      </div>
      <CruceManual c={c} origen={origenCruce} alCerrar={() => setOrigenCruce(null)} />
    </section>
  )
}

// ------------------------------------------------------------------ por revisar

function PorRevisar({ c, cruces, editable }: { c: Conciliacion; cruces: Cruce[]; editable: boolean }) {
  const acciones = useAccionConciliacion(c.id)
  if (cruces.length === 0) {
    return (
      <Vacio icono={CheckCircle2} titulo="No hay cruces por revisar">
        Los cruces por nº de cheque y los de monto y fecha sin ambigüedad se aceptan solos.
      </Vacio>
    )
  }
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3">
        <p className="text-sm text-slate-600">
          El sistema propone estos pares, pero hay ambigüedad (varios del mismo monto) o fechas
          lejanas. Confirme si corresponden o deshaga el cruce.
        </p>
        {editable && (
          <Boton
            variante="exito"
            icono={CheckCheck}
            cargando={acciones.confirmarTodos.isPending}
            onClick={() =>
              acciones.confirmarTodos.mutate(undefined, {
                onSuccess: () => toast.success(`${cruces.length} cruces confirmados`),
                onError: (e) => toast.error(e.message),
              })
            }
          >
            Confirmar todos ({cruces.length})
          </Boton>
        )}
      </div>
      <ul className="divide-y divide-slate-100">
        {cruces.map((x) => (
          <TarjetaCruce key={x.id} c={c} cruce={x} editable={editable} />
        ))}
      </ul>
    </div>
  )
}

function TarjetaCruce({ c, cruce, editable }: { c: Conciliacion; cruce: Cruce; editable: boolean }) {
  const acciones = useAccionConciliacion(c.id)
  const { partida: p, movimiento: m } = cruce
  return (
    <li className="px-5 py-4">
      <div className="grid items-stretch gap-3 md:grid-cols-[1fr_auto_1fr]">
        <div className="rounded-lg bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
          <p className="mb-1 flex items-center gap-2 text-xs font-medium tracking-wide text-slate-500 uppercase">
            Libro · {p.tipo === 'INGRESO' ? 'Ingreso' : 'Egreso'} #{p.comprobante ?? '—'}
            <OrigenPartida p={p} />
          </p>
          <p className="text-sm text-slate-800">
            <DescripcionPartida p={p} />
          </p>
          <p className="mt-1 flex justify-between text-sm">
            <span className="text-slate-500">{fecha(p.fecha)}</span>
            <strong className="monto">{pesos(p.monto)}</strong>
          </p>
        </div>
        <div className="flex items-center justify-center text-slate-300">
          <ArrowRightLeft className="size-5" aria-hidden />
        </div>
        <div className="rounded-lg bg-slate-50 px-4 py-3 ring-1 ring-slate-200">
          <p className="mb-1 text-xs font-medium tracking-wide text-slate-500 uppercase">
            Banco · {m.es_cargo ? 'Cargo' : 'Abono'}
          </p>
          <p className="text-sm text-slate-800">
            <DescripcionMovimiento m={m} />
          </p>
          <p className="mt-1 flex justify-between text-sm">
            <span className="text-slate-500">{fecha(m.fecha)}</span>
            <strong className="monto">{pesos(m.monto)}</strong>
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-amber-800">{cruce.nota}</p>
        {editable && (
          <div className="flex gap-2">
            <Boton
              tamano="sm"
              variante="secundario"
              icono={Undo2}
              cargando={acciones.deshacerCruce.isPending && acciones.deshacerCruce.variables === cruce.id}
              onClick={() =>
                acciones.deshacerCruce.mutate(cruce.id, {
                  onSuccess: () => toast('Cruce deshecho: ambos vuelven a pendientes'),
                  onError: (e) => toast.error(e.message),
                })
              }
            >
              No corresponde
            </Boton>
            <Boton
              tamano="sm"
              variante="exito"
              icono={CheckCircle2}
              cargando={acciones.confirmarCruce.isPending && acciones.confirmarCruce.variables === cruce.id}
              onClick={() =>
                acciones.confirmarCruce.mutate(cruce.id, { onError: (e) => toast.error(e.message) })
              }
            >
              Confirmar
            </Boton>
          </div>
        )}
      </div>
    </li>
  )
}

// ------------------------------------------------------------------ pendientes

function TablaPartidas({
  partidas,
  vacio,
  puedeCruzar,
  alCruzar,
}: {
  partidas: Partida[]
  vacio: string
  puedeCruzar: (p: Partida) => boolean
  alCruzar: (p: Partida) => void
}) {
  if (partidas.length === 0) return <Vacio icono={CheckCircle2} titulo="Sin pendientes">{vacio}</Vacio>
  const total = partidas.reduce((t, p) => t + p.monto, 0)
  const egresos = partidas[0].tipo === 'EGRESO'
  return (
    <Tabla
      cabeceras={['Fecha', 'Nº', egresos ? 'Nº cheque' : 'Depto', 'Detalle', { texto: 'Monto', derecha: true }, '']}
    >
      {partidas.map((p) => (
        <tr key={p.id} className="hover:bg-slate-50">
          <Celda className="whitespace-nowrap text-slate-600">{fecha(p.fecha)}</Celda>
          <Celda className="font-medium">{p.comprobante ?? '—'}</Celda>
          <Celda>{egresos ? p.cheque || '—' : p.depto || '—'}</Celda>
          <Celda>
            <div className="flex flex-wrap items-center gap-2">
              <span className="max-w-xl">{egresos ? p.glosa : p.glosa || 'G.C.'}</span>
              <OrigenPartida p={p} />
            </div>
          </Celda>
          <Celda derecha>{pesos(p.monto)}</Celda>
          <Celda className="text-right">
            {puedeCruzar(p) && (
              <Boton tamano="sm" variante="fantasma" icono={ArrowRightLeft} onClick={() => alCruzar(p)}>
                Cruzar…
              </Boton>
            )}
          </Celda>
        </tr>
      ))}
      <FilaTotal columnas={4} total={total} />
    </Tabla>
  )
}

function TablaMovimientos({
  movimientos,
  puedeCruzar,
  alCruzar,
}: {
  movimientos: Movimiento[]
  puedeCruzar: (m: Movimiento) => boolean
  alCruzar: (m: Movimiento) => void
}) {
  if (movimientos.length === 0) {
    return (
      <Vacio icono={CheckCircle2} titulo="Sin movimientos no contabilizados">
        Todo lo que aparece en la cartola está registrado en las planillas.
      </Vacio>
    )
  }
  const total = movimientos.reduce((t, m) => t + (m.es_cargo ? -m.monto : m.monto), 0)
  return (
    <>
      <p className="border-b border-slate-100 px-5 py-3 text-sm text-slate-600">
        Movimientos del banco que no están en las planillas. Si corresponden a un ingreso o egreso
        aún no registrado, regístrelo en la planilla y vuelva a subirla; el cruce se hará solo.
      </p>
      <Tabla cabeceras={['Fecha', 'Descripción', 'Sucursal', { texto: 'Monto', derecha: true }, '']}>
        {movimientos.map((m) => (
          <tr key={m.id} className="hover:bg-slate-50">
            <Celda className="whitespace-nowrap text-slate-600">{fecha(m.fecha)}</Celda>
            <Celda>
              <div className="flex flex-wrap items-center gap-2">
                <DescripcionMovimiento m={m} />
                {m.origen === 'arrastre' && <Insignia tono="violeta">Mes anterior</Insignia>}
              </div>
            </Celda>
            <Celda className="text-slate-500">{m.sucursal || '—'}</Celda>
            <Celda derecha>
              <MontoMovimiento m={m} />
            </Celda>
            <Celda className="text-right">
              {puedeCruzar(m) && (
                <Boton tamano="sm" variante="fantasma" icono={ArrowRightLeft} onClick={() => alCruzar(m)}>
                  Cruzar…
                </Boton>
              )}
            </Celda>
          </tr>
        ))}
        <FilaTotal columnas={3} total={total} />
      </Tabla>
    </>
  )
}

function FilaTotal({ columnas, total }: { columnas: number; total: number }) {
  return (
    <tr className="bg-slate-50 font-semibold text-slate-900">
      <td colSpan={columnas} className="px-4 py-2.5 text-right text-xs tracking-wide text-slate-500 uppercase">
        Total
      </td>
      <td className="monto px-4 py-2.5 text-right">{pesos(total)}</td>
      <td />
    </tr>
  )
}

// ------------------------------------------------------------------ todos los cruces

function TodosLosCruces({ c, editable }: { c: Conciliacion; editable: boolean }) {
  const acciones = useAccionConciliacion(c.id)
  const [busqueda, setBusqueda] = useState('')
  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    if (!q) return c.cruces
    return c.cruces.filter((x) =>
      [x.partida.comprobante, x.partida.glosa, x.partida.depto, x.partida.cheque, x.movimiento.descripcion, x.movimiento.documento, x.partida.monto]
        .join(' ')
        .toLowerCase()
        .includes(q),
    )
  }, [busqueda, c.cruces])

  if (c.cruces.length === 0) {
    return <Vacio icono={ArrowRightLeft} titulo="Sin cruces">No se cruzó ningún movimiento.</Vacio>
  }
  return (
    <>
      <div className="border-b border-slate-100 px-5 py-3">
        <div className="relative max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            placeholder="Buscar por comprobante, cheque, depto, monto…"
            aria-label="Buscar cruces"
            className="w-full rounded-lg border-0 py-1.5 pr-3 pl-9 text-sm ring-1 ring-slate-300 ring-inset focus:ring-2 focus:ring-marca-600 focus:outline-none"
          />
        </div>
      </div>
      <Tabla cabeceras={['Libro', 'Banco', { texto: 'Monto', derecha: true }, 'Cruce', '']}>
        {filtrados.map((x) => (
          <tr key={x.id} className="hover:bg-slate-50">
            <Celda>
              <p className="font-medium">
                {x.partida.tipo === 'INGRESO' ? 'Ingreso' : 'Egreso'} #{x.partida.comprobante ?? '—'}
                <span className="font-normal text-slate-500"> · {fecha(x.partida.fecha)}</span>
              </p>
              <p className="text-xs text-slate-500">
                <DescripcionPartida p={x.partida} />
              </p>
            </Celda>
            <Celda>
              <p className="text-slate-600">{fecha(x.movimiento.fecha)}</p>
              <p className="text-xs text-slate-500">
                <DescripcionMovimiento m={x.movimiento} />
              </p>
            </Celda>
            <Celda derecha>{pesos(x.partida.monto)}</Celda>
            <Celda>
              <div className="flex flex-col items-start gap-1">
                <InsigniaTipoCruce tipo={x.tipo} />
                {x.confirmado && x.confirmado_por && (
                  <span className="text-xs text-slate-500">Confirmó {x.confirmado_por}</span>
                )}
              </div>
            </Celda>
            <Celda className="text-right">
              {editable && (
                <Boton
                  tamano="sm"
                  variante="fantasma"
                  icono={Undo2}
                  onClick={() =>
                    acciones.deshacerCruce.mutate(x.id, {
                      onSuccess: () => toast('Cruce deshecho'),
                      onError: (e) => toast.error(e.message),
                    })
                  }
                >
                  Deshacer
                </Boton>
              )}
            </Celda>
          </tr>
        ))}
      </Tabla>
    </>
  )
}

// ------------------------------------------------------------------ advertencias e historial

function Advertencias({ c }: { c: Conciliacion }) {
  if (c.advertencias.length === 0 && c.movimientos_repetidos.length === 0) {
    return <Vacio icono={CheckCircle2} titulo="Sin advertencias">Los archivos se leyeron sin observaciones.</Vacio>
  }
  return (
    <div className="space-y-4 p-5">
      {c.advertencias.length > 0 && (
        <ul className="space-y-2">
          {c.advertencias.map((a, i) => (
            <li key={i} className="rounded-lg bg-amber-50 px-4 py-2.5 text-sm text-amber-900 ring-1 ring-amber-200">
              {a}
            </li>
          ))}
        </ul>
      )}
      {c.movimientos_repetidos.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-900">
            Movimientos descartados por venir también en la cartola anterior
          </h3>
          <Tabla cabeceras={['Fecha', 'Descripción', { texto: 'Monto', derecha: true }]}>
            {c.movimientos_repetidos.map((m) => (
              <tr key={m.id}>
                <Celda>{fecha(m.fecha)}</Celda>
                <Celda>
                  <DescripcionMovimiento m={m} />
                </Celda>
                <Celda derecha>
                  <MontoMovimiento m={m} />
                </Celda>
              </tr>
            ))}
          </Tabla>
        </div>
      )}
    </div>
  )
}

const ACCIONES: Record<string, string> = {
  importada: 'Saldo inicial cargado',
  creada: 'Mes creado',
  archivo: 'Archivo cargado',
  procesada: 'Procesada',
  cruce_confirmado: 'Cruce confirmado',
  cruce_deshecho: 'Cruce deshecho',
  cruce_manual: 'Cruce manual',
  redondeo: 'Redondeo ajustado',
  cerrada: 'Mes cerrado',
  reabierta: 'Mes reabierto',
}

function Historial({ c }: { c: Conciliacion }) {
  if (c.eventos.length === 0) return <Vacio icono={History} titulo="Sin actividad" />
  return (
    <ol className="divide-y divide-slate-100">
      {c.eventos.map((e) => (
        <li key={e.id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-3 text-sm">
          <span>
            <span className="font-medium text-slate-900">{ACCIONES[e.accion] ?? e.accion}</span>
            {e.detalle && <span className="text-slate-600"> · {e.detalle}</span>}
          </span>
          <span className="text-xs text-slate-500">
            {fechaHora(e.fecha)} · {e.usuario ?? 'Sistema'}
          </span>
        </li>
      ))}
    </ol>
  )
}
