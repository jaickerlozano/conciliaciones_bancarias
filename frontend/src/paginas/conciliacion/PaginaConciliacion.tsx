import { Lock, RotateCcw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import { useAccionConciliacion, useConciliacion } from '../../api/consultas'
import type { Conciliacion } from '../../api/tipos'
import { EncabezadoPagina, Migas } from '../../componentes/Marco'
import { Boton } from '../../componentes/ui/Boton'
import { Entrada } from '../../componentes/ui/Campos'
import { Cargando, ErrorCarga } from '../../componentes/ui/Estados'
import { InsigniaEstado } from '../../componentes/ui/Insignia'
import { Modal } from '../../componentes/ui/Modal'
import { fechaHora, nombrePeriodo } from '../../lib/formato'
import { Archivos } from './Archivos'
import { Pasos } from './Pasos'
import { Resumen } from './Resumen'
import { Revision } from './Revision'

export function PaginaConciliacion() {
  const id = Number(useParams().id)
  const { data: c, isPending, error } = useConciliacion(id)

  if (isPending) return <Cargando />
  if (error) return <ErrorCarga error={error} />

  const titulo =
    c.estado === 'importada'
      ? `Saldo inicial · ${nombrePeriodo(c.periodo)}`
      : `Conciliación ${nombrePeriodo(c.periodo)}`

  return (
    <>
      <Migas
        items={[
          { texto: 'Comunidades', a: '/comunidades' },
          { texto: c.comunidad_nombre, a: `/comunidades/${c.comunidad_id}` },
          { texto: nombrePeriodo(c.periodo) },
        ]}
      />
      <EncabezadoPagina
        titulo={titulo}
        insignia={<InsigniaEstado estado={c.estado} />}
        subtitulo={
          <>
            {c.banco_nombre} · {c.cuenta_numero}
            {c.cerrada_en && (
              <>
                {' '}
                · Cerrada el {fechaHora(c.cerrada_en)}
                {c.cerrada_por && ` por ${c.cerrada_por}`}
              </>
            )}
          </>
        }
        acciones={<Acciones c={c} />}
      />

      {c.estado === 'importada' ? (
        <div className="space-y-6">
          <p className="rounded-xl bg-violet-50 px-4 py-3 text-sm text-violet-900 ring-1 ring-violet-200">
            Este es el punto de partida de la cuenta: los pendientes de abajo se cruzarán contra la
            cartola del mes siguiente.
          </p>
          <Resumen c={c} />
          <Revision c={c} />
        </div>
      ) : (
        <>
          <Pasos c={c} />
          {c.estado === 'borrador' ? (
            <Archivos c={c} />
          ) : (
            <div className="space-y-6">
              <Resumen c={c} />
              <Revision c={c} />
              <Archivos c={c} compacto />
            </div>
          )}
        </>
      )}
    </>
  )
}

function Acciones({ c }: { c: Conciliacion }) {
  const acciones = useAccionConciliacion(c.id)
  const navegar = useNavigate()
  const [dialogo, setDialogo] = useState<'cerrar' | 'reabrir' | 'eliminar' | null>(null)
  const [motivo, setMotivo] = useState('')
  const r = c.resumen

  const razonNoCierra =
    r.diferencia !== 0
      ? 'La diferencia debe ser $0'
      : r.cruces_por_revisar > 0
        ? `Quedan ${r.cruces_por_revisar} cruces por revisar`
        : null

  const cerrarDialogo = () => {
    setDialogo(null)
    setMotivo('')
  }

  return (
    <>
      {c.estado !== 'cerrada' && (
        <Boton variante="fantasma" icono={Trash2} onClick={() => setDialogo('eliminar')}>
          Eliminar
        </Boton>
      )}
      {c.estado === 'cerrada' && (
        <Boton variante="secundario" icono={RotateCcw} onClick={() => setDialogo('reabrir')}>
          Reabrir
        </Boton>
      )}
      {c.estado === 'procesada' && (
        <span title={razonNoCierra ?? undefined}>
          <Boton icono={Lock} disabled={razonNoCierra !== null} onClick={() => setDialogo('cerrar')}>
            Cerrar mes
          </Boton>
        </span>
      )}

      <Modal
        abierto={dialogo === 'cerrar'}
        alCerrar={cerrarDialogo}
        titulo={`¿Cerrar ${nombrePeriodo(c.periodo)}?`}
        pie={
          <>
            <Boton variante="secundario" onClick={cerrarDialogo}>
              Cancelar
            </Boton>
            <Boton
              icono={Lock}
              cargando={acciones.cerrar.isPending}
              onClick={() =>
                acciones.cerrar.mutate(undefined, {
                  onSuccess: () => {
                    toast.success(`${nombrePeriodo(c.periodo)} cerrado`)
                    cerrarDialogo()
                  },
                  onError: (e) => toast.error(e.message),
                })
              }
            >
              Cerrar mes
            </Boton>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          La conciliación quedará bloqueada y sus pendientes pasarán al mes siguiente. Podrá
          reabrirla indicando un motivo mientras no exista el mes siguiente.
        </p>
      </Modal>

      <Modal
        abierto={dialogo === 'reabrir'}
        alCerrar={cerrarDialogo}
        titulo={`Reabrir ${nombrePeriodo(c.periodo)}`}
        pie={
          <>
            <Boton variante="secundario" onClick={cerrarDialogo}>
              Cancelar
            </Boton>
            <Boton
              icono={RotateCcw}
              disabled={!motivo.trim()}
              cargando={acciones.reabrir.isPending}
              onClick={() =>
                acciones.reabrir.mutate(motivo, {
                  onSuccess: () => {
                    toast.success('Conciliación reabierta')
                    cerrarDialogo()
                  },
                  onError: (e) => toast.error(e.message),
                })
              }
            >
              Reabrir
            </Boton>
          </>
        }
      >
        <Entrada
          etiqueta="Motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          placeholder="Ej.: se registró mal un depósito"
          ayuda="Queda registrado en el historial."
          autoFocus
        />
      </Modal>

      <Modal
        abierto={dialogo === 'eliminar'}
        alCerrar={cerrarDialogo}
        titulo={c.estado === 'importada' ? '¿Eliminar el saldo inicial?' : `¿Eliminar ${nombrePeriodo(c.periodo)}?`}
        pie={
          <>
            <Boton variante="secundario" onClick={cerrarDialogo}>
              Cancelar
            </Boton>
            <Boton
              variante="peligro"
              icono={Trash2}
              cargando={acciones.eliminar.isPending}
              onClick={() =>
                acciones.eliminar.mutate(undefined, {
                  onSuccess: () => {
                    toast.success('Eliminada')
                    navegar(`/comunidades/${c.comunidad_id}`)
                  },
                  onError: (e) => toast.error(e.message),
                })
              }
            >
              Eliminar
            </Boton>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          Se borrarán los archivos cargados, los cruces y el historial de este mes. Esta acción no
          se puede deshacer.
        </p>
      </Modal>
    </>
  )
}
