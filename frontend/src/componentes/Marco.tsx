import { ChevronRight, LogOut, ShieldCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router'
import { toast } from 'sonner'

import { useSesion } from '../sesion/contexto'

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid size-8 place-items-center rounded-lg bg-marca-700 text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="size-5" aria-hidden>
          <path
            d="M6 12.5l4 4L18 8"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.6"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <span className="leading-tight">
        <span className="block text-sm font-semibold text-slate-900">Conciliaciones</span>
        <span className="block text-xs text-slate-500">Gaudi Administraciones</span>
      </span>
    </span>
  )
}

export function Marco() {
  const { usuario, salir } = useSesion()
  const navegar = useNavigate()

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-8">
            <Link to="/comunidades">
              <Logo />
            </Link>
            <nav className="hidden sm:block">
              <NavLink
                to="/comunidades"
                className={({ isActive }) =>
                  `rounded-md px-3 py-2 text-sm font-medium ${
                    isActive ? 'bg-marca-50 text-marca-800' : 'text-slate-600 hover:bg-slate-100'
                  }`
                }
              >
                Comunidades
              </NavLink>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            {usuario?.es_admin && (
              <a
                href="/admin/"
                className="hidden items-center gap-1 text-xs text-slate-500 hover:text-slate-800 md:flex"
                title="Administración técnica (solo superusuario)"
              >
                <ShieldCheck className="size-4" aria-hidden />
                Admin
              </a>
            )}
            <div className="text-right">
              <p className="text-sm font-medium text-slate-800">{usuario?.nombre}</p>
              <p className="text-xs text-slate-500">{usuario?.usuario}</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                await salir()
                toast.success('Sesión cerrada')
                navegar('/ingresar')
              }}
              className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              title="Cerrar sesión"
              aria-label="Cerrar sesión"
            >
              <LogOut className="size-5" />
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>
    </div>
  )
}

export function Migas({ items }: { items: { texto: string; a?: string }[] }) {
  return (
    <nav aria-label="Ruta" className="mb-3 flex flex-wrap items-center gap-1 text-sm text-slate-500">
      {items.map((item, i) => (
        <span key={item.texto} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="size-4 text-slate-300" aria-hidden />}
          {item.a ? (
            <Link to={item.a} className="hover:text-marca-700 hover:underline">
              {item.texto}
            </Link>
          ) : (
            <span className="text-slate-700">{item.texto}</span>
          )}
        </span>
      ))}
    </nav>
  )
}

export function EncabezadoPagina({
  titulo,
  subtitulo,
  acciones,
  insignia,
}: {
  titulo: string
  subtitulo?: ReactNode
  acciones?: ReactNode
  insignia?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{titulo}</h1>
          {insignia}
        </div>
        {subtitulo && <p className="mt-1 text-sm text-slate-500">{subtitulo}</p>}
      </div>
      {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
    </div>
  )
}
