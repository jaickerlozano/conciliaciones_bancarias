import clsx from 'clsx'
import type { ReactNode } from 'react'

export function Tarjeta({
  titulo,
  subtitulo,
  acciones,
  children,
  className,
  sinRelleno = false,
}: {
  titulo?: ReactNode
  subtitulo?: ReactNode
  acciones?: ReactNode
  children: ReactNode
  className?: string
  sinRelleno?: boolean
}) {
  return (
    <section
      className={clsx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}
    >
      {(titulo || acciones) && (
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <div>
            {titulo && <h2 className="text-sm font-semibold text-slate-900">{titulo}</h2>}
            {subtitulo && <p className="text-xs text-slate-500">{subtitulo}</p>}
          </div>
          {acciones && <div className="flex flex-wrap items-center gap-2">{acciones}</div>}
        </header>
      )}
      <div className={sinRelleno ? '' : 'p-5'}>{children}</div>
    </section>
  )
}
