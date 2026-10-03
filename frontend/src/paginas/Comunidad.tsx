import { CalendarPlus, ChevronRight, Landmark, Pencil, Plus, Wallet } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'

import {
  useComunidad,
  useConciliacionesDeCuenta,
  useCrearConciliacion,
} from '../api/consultas'
import type { Cuenta } from '../api/tipos'
import { EncabezadoPagina, Migas } from '../componentes/Marco'
import { Boton } from '../componentes/ui/Boton'
import { Cargando, ErrorCarga, Vacio } from '../componentes/ui/Estados'
import { Insignia, InsigniaEstado } from '../componentes/ui/Insignia'
import { Tarjeta } from '../componentes/ui/Tarjeta'
import { fechaHora, nombrePeriodo, periodoSiguiente, pesos } from '../lib/formato'
import { FormularioComunidad } from './FormularioComunidad'
import { FormularioCuenta } from './FormularioCuenta'
import { SaldoInicial } from './SaldoInicial'

export function PaginaComunidad() {
  const id = Number(useParams().id)
  const { data: comunidad, isPending, error } = useComunidad(id)
  const [editando, setEditando] = useState(false)
  const [cuentaEditada, setCuentaEditada] = useState<Cuenta | 'nueva' | null>(null)

  if (isPending) return <Cargando />
  if (error) return <ErrorCarga error={error} />

  return (
    <>
      <Migas items={[{ texto: 'Comunidades', a: '/comunidades' }, { texto: comunidad.nombre }]} />
      <EncabezadoPagina
        titulo={comunidad.nombre}
        subtitulo={[comunidad.rut, comunidad.direccion].filter(Boolean).join(' · ') || undefined}
        insignia={!comunidad.activa && <Insignia>Inactiva</Insignia>}
        acciones={
          <>
            <Boton variante="secundario" icono={Pencil} onClick={() => setEditando(true)}>
              Editar
            </Boton>
            <Boton icono={Plus} onClick={() => setCuentaEditada('nueva')}>
              Agregar cuenta
            </Boton>
          </>
        }
      />

      {comunidad.cuentas.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white">
          <Vacio
            icono={Landmark}
            titulo="Esta comunidad no tiene cuentas bancarias"
            accion={
              <Boton icono={Plus} onClick={() => setCuentaEditada('nueva')}>
                Agregar cuenta
              </Boton>
            }
          >
            Agregue la cuenta corriente de la comunidad para empezar a conciliar.
          </Vacio>
        </div>
      ) : (
        <div className="space-y-6">
          {comunidad.cuentas.map((cuenta) => (
            <TarjetaCuenta key={cuenta.id} cuenta={cuenta} alEditar={() => setCuentaEditada(cuenta)} />
          ))}
        </div>
      )}

      <FormularioComunidad abierto={editando} alCerrar={() => setEditando(false)} comunidad={comunidad} />
      <FormularioCuenta
        abierto={cuentaEditada !== null}
        alCerrar={() => setCuentaEditada(null)}
        comunidad={comunidad.id}
        cuenta={cuentaEditada === 'nueva' ? undefined : (cuentaEditada ?? undefined)}
      />
    </>
  )
}

function TarjetaCuenta({ cuenta, alEditar }: { cuenta: Cuenta; alEditar: () => void }) {
  const { data: meses, isPending, error } = useConciliacionesDeCuenta(cuenta.id)
  const crear = useCrearConciliacion()
  const navegar = useNavigate()
  const [saldoInicial, setSaldoInicial] = useState(false)

  const ultimo = meses?.[0]
  const listoParaSiguiente = ultimo && ['cerrada', 'importada'].includes(ultimo.estado)
  const siguiente = ultimo ? periodoSiguiente(ultimo.periodo) : null

  const iniciarMes = () => {
    if (!siguiente) return
    crear.mutate(
      { cuenta: cuenta.id, periodo: siguiente },
      {
        onSuccess: (c) => {
          toast.success(`${nombrePeriodo(c.periodo)} creado. Suba los archivos del mes.`)
          navegar(`/conciliaciones/${c.id}`)
        },
        onError: (e) => toast.error(e.message),
      },
    )
  }

  return (
    <Tarjeta
      sinRelleno
      titulo={
        <span className="flex items-center gap-2">
          <Landmark className="size-4 text-slate-400" aria-hidden />
          {cuenta.banco_nombre} · {cuenta.numero}
          {!cuenta.activa && <Insignia>Inactiva</Insignia>}
        </span>
      }
      subtitulo="Cuenta corriente"
      acciones={
        <>
          <Boton variante="fantasma" tamano="sm" icono={Pencil} onClick={alEditar}>
            Editar cuenta
          </Boton>
          {meses && meses.length === 0 && (
            <Boton icono={Wallet} onClick={() => setSaldoInicial(true)}>
              Configurar saldo inicial
            </Boton>
          )}
          {ultimo && (
            <span title={listoParaSiguiente ? undefined : `Cierre ${nombrePeriodo(ultimo.periodo)} antes de seguir`}>
              <Boton
                icono={CalendarPlus}
                disabled={!listoParaSiguiente}
                cargando={crear.isPending}
                onClick={iniciarMes}
              >
                Iniciar {siguiente && nombrePeriodo(siguiente)}
              </Boton>
            </span>
          )}
        </>
      }
    >
      {ultimo && !listoParaSiguiente && (
        <p className="border-b border-slate-100 bg-amber-50/60 px-5 py-2 text-xs text-amber-900">
          Para iniciar {siguiente && nombrePeriodo(siguiente)}, primero cierre{' '}
          {nombrePeriodo(ultimo.periodo)}
          {ultimo.resumen.cruces_por_revisar > 0 &&
            ` (le quedan ${ultimo.resumen.cruces_por_revisar} cruces por revisar)`}
          .
        </p>
      )}
      {isPending ? (
        <Cargando />
      ) : error ? (
        <div className="p-5">
          <ErrorCarga error={error} />
        </div>
      ) : meses.length === 0 ? (
        <Vacio icono={Wallet} titulo="Falta el saldo inicial">
          Antes del primer mes, indique con qué saldos y pendientes parte esta cuenta: a mano o
          importándolos desde la planilla de conciliación que usaban hasta ahora.
        </Vacio>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-5 py-2.5">Mes</th>
                <th className="px-5 py-2.5">Estado</th>
                <th className="px-5 py-2.5 text-right">Saldo banco</th>
                <th className="px-5 py-2.5 text-right">Diferencia</th>
                <th className="hidden px-5 py-2.5 lg:table-cell">Cierre</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {meses.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => navegar(`/conciliaciones/${m.id}`)}
                  className="cursor-pointer hover:bg-slate-50"
                >
                  <td className="px-5 py-3 font-medium text-slate-900">{nombrePeriodo(m.periodo)}</td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <InsigniaEstado estado={m.estado} />
                      {m.estado === 'procesada' && m.resumen.cruces_por_revisar > 0 && (
                        <Insignia tono="ambar">{m.resumen.cruces_por_revisar} por revisar</Insignia>
                      )}
                    </div>
                  </td>
                  <td className="monto px-5 py-3 text-right text-slate-700">{pesos(m.resumen.saldo_banco)}</td>
                  <td className="monto px-5 py-3 text-right">
                    {m.resumen.diferencia === null ? (
                      <span className="text-slate-400">—</span>
                    ) : m.resumen.diferencia === 0 ? (
                      <span className="font-medium text-emerald-700">$0</span>
                    ) : (
                      <span className="font-medium text-rose-700">{pesos(m.resumen.diferencia)}</span>
                    )}
                  </td>
                  <td className="hidden px-5 py-3 text-slate-500 lg:table-cell">
                    {m.cerrada_en ? fechaHora(m.cerrada_en) : '—'}
                  </td>
                  <td className="pr-4 text-slate-300">
                    <ChevronRight className="size-5" aria-hidden />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SaldoInicial abierto={saldoInicial} alCerrar={() => setSaldoInicial(false)} cuenta={cuenta} />
    </Tarjeta>
  )
}
