import { Building2, ChevronRight, Landmark, Plus, Search } from 'lucide-react'
import { useDeferredValue, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'

import { useComunidades, type FiltroComunidades } from '../api/consultas'
import type { Cuenta } from '../api/tipos'
import { EncabezadoPagina } from '../componentes/Marco'
import { Boton } from '../componentes/ui/Boton'
import { Cargando, ErrorCarga, Vacio } from '../componentes/ui/Estados'
import { InsigniaEstado } from '../componentes/ui/Insignia'
import { nombrePeriodo } from '../lib/formato'
import { FormularioComunidad } from './FormularioComunidad'

export function PaginaComunidades() {
  // los filtros viven en la URL: se conservan al volver atrás
  const [params, setParams] = useSearchParams()
  const q = params.get('q') ?? ''
  const activa = (params.get('activa') ?? 'true') as FiltroComunidades['activa']
  const qDiferida = useDeferredValue(q)
  const { data, isPending, error, isFetching } = useComunidades({ q: qDiferida, activa })
  const [creando, setCreando] = useState(false)
  const navegar = useNavigate()

  const cambiar = (clave: string, valor: string) =>
    setParams(
      (p) => {
        p.set(clave, valor)
        return p
      },
      { replace: true },
    )

  return (
    <>
      <EncabezadoPagina
        titulo="Comunidades"
        subtitulo="Elija una comunidad para ver sus cuentas y conciliaciones mensuales."
        acciones={
          <Boton icono={Plus} onClick={() => setCreando(true)}>
            Nueva comunidad
          </Boton>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-64 flex-1 sm:max-w-sm">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={q}
            onChange={(e) => cambiar('q', e.target.value)}
            placeholder="Buscar por nombre, RUT o dirección"
            aria-label="Buscar comunidades"
            className="w-full rounded-lg border-0 bg-white py-2 pr-3 pl-9 text-sm shadow-sm ring-1 ring-slate-300 ring-inset placeholder:text-slate-400 focus:ring-2 focus:ring-marca-600 focus:outline-none"
          />
        </div>
        <div className="inline-flex rounded-lg bg-white p-0.5 shadow-sm ring-1 ring-slate-300" role="group">
          {(
            [
              ['true', 'Activas'],
              ['false', 'Inactivas'],
              ['', 'Todas'],
            ] as const
          ).map(([valor, texto]) => (
            <button
              key={texto}
              type="button"
              onClick={() => cambiar('activa', valor)}
              aria-pressed={activa === valor}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                activa === valor ? 'bg-marca-700 text-white' : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {texto}
            </button>
          ))}
        </div>
        {isFetching && !isPending && <span className="text-xs text-slate-400">Actualizando…</span>}
      </div>

      {isPending ? (
        <Cargando />
      ) : error ? (
        <ErrorCarga error={error} />
      ) : data.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white">
          <Vacio
            icono={Building2}
            titulo={q ? 'Sin resultados' : 'Aún no hay comunidades'}
            accion={
              !q && (
                <Boton icono={Plus} onClick={() => setCreando(true)}>
                  Crear la primera
                </Boton>
              )
            }
          >
            {q ? `Ninguna comunidad coincide con “${q}”.` : 'Cree una comunidad para empezar.'}
          </Vacio>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 text-left text-xs font-medium tracking-wide text-slate-500 uppercase">
              <tr>
                <th className="px-5 py-3">Comunidad</th>
                <th className="hidden px-5 py-3 md:table-cell">Cuentas</th>
                <th className="px-5 py-3">Último mes</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.map((c) => (
                <tr
                  key={c.id}
                  onClick={() => navegar(`/comunidades/${c.id}`)}
                  className="cursor-pointer hover:bg-slate-50"
                >
                  <td className="px-5 py-4">
                    <Link
                      to={`/comunidades/${c.id}`}
                      className="font-medium text-slate-900 hover:text-marca-700"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {c.nombre}
                    </Link>
                    <p className="text-xs text-slate-500">
                      {[c.rut, c.direccion].filter(Boolean).join(' · ') || '—'}
                      {!c.activa && ' · Inactiva'}
                    </p>
                  </td>
                  <td className="hidden px-5 py-4 md:table-cell">
                    <div className="flex flex-wrap gap-1.5">
                      {c.cuentas.length === 0 ? (
                        <span className="text-xs text-slate-400">Sin cuentas</span>
                      ) : (
                        c.cuentas.map((cuenta) => (
                          <span
                            key={cuenta.id}
                            className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
                          >
                            <Landmark className="size-3" aria-hidden />
                            {cuenta.banco_nombre} {cuenta.numero}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <UltimosMeses cuentas={c.cuentas} />
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

      <FormularioComunidad
        abierto={creando}
        alCerrar={() => setCreando(false)}
        alGuardar={(c) => navegar(`/comunidades/${c.id}`)}
      />
    </>
  )
}

function UltimosMeses({ cuentas }: { cuentas: Cuenta[] }) {
  const ultimos = cuentas.filter((c) => c.ultima_conciliacion)
  if (ultimos.length === 0) return <span className="text-xs text-slate-400">Sin conciliaciones</span>
  return (
    <div className="space-y-1">
      {ultimos.map((c) => (
        <div key={c.id} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-700">{nombrePeriodo(c.ultima_conciliacion!.periodo)}</span>
          <InsigniaEstado estado={c.ultima_conciliacion!.estado} />
        </div>
      ))}
    </div>
  )
}
