import clsx from 'clsx'
import { AlertTriangle, Loader2, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

export function Cargando({ texto = 'Cargando…', pantallaCompleta = false }) {
  return (
    <div
      role="status"
      className={clsx(
        'flex items-center justify-center gap-2 text-sm text-slate-500',
        pantallaCompleta ? 'min-h-screen' : 'py-16',
      )}
    >
      <Loader2 className="size-5 animate-spin text-marca-600" aria-hidden />
      {texto}
    </div>
  )
}

export function ErrorCarga({ error }: { error: unknown }) {
  const mensaje = error instanceof Error ? error.message : 'No se pudo cargar la información.'
  return (
    <div className="flex items-center gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <AlertTriangle className="size-5 shrink-0" aria-hidden />
      {mensaje}
    </div>
  )
}

export function Vacio({
  icono: Icono,
  titulo,
  children,
  accion,
}: {
  icono: LucideIcon
  titulo: string
  children?: ReactNode
  accion?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-slate-100 p-3">
        <Icono className="size-6 text-slate-400" aria-hidden />
      </div>
      <h3 className="text-sm font-semibold text-slate-900">{titulo}</h3>
      {children && <p className="mt-1 max-w-sm text-sm text-slate-500">{children}</p>}
      {accion && <div className="mt-4">{accion}</div>}
    </div>
  )
}
