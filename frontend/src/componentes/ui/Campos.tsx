import clsx from 'clsx'
import { useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'

const BASE_CONTROL =
  'block w-full rounded-lg border-0 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm ' +
  'ring-1 ring-inset ring-slate-300 placeholder:text-slate-400 ' +
  'focus:ring-2 focus:ring-inset focus:ring-marca-600 focus:outline-none ' +
  'disabled:bg-slate-50 disabled:text-slate-500'

interface Envoltura {
  etiqueta?: string
  ayuda?: ReactNode
  error?: string
}

function Envolver({
  id,
  etiqueta,
  ayuda,
  error,
  children,
}: Envoltura & { id: string; children: ReactNode }) {
  return (
    <div>
      {etiqueta && (
        <label htmlFor={id} className="mb-1 block text-sm font-medium text-slate-700">
          {etiqueta}
        </label>
      )}
      {children}
      {error ? (
        <p className="mt-1 text-xs text-rose-600">{error}</p>
      ) : (
        ayuda && <p className="mt-1 text-xs text-slate-500">{ayuda}</p>
      )}
    </div>
  )
}

export function Entrada({
  etiqueta,
  ayuda,
  error,
  className,
  ...resto
}: Envoltura & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <Envolver id={id} etiqueta={etiqueta} ayuda={ayuda} error={error}>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        className={clsx(BASE_CONTROL, error && 'ring-rose-400', className)}
        {...resto}
      />
    </Envolver>
  )
}

export function Selector({
  etiqueta,
  ayuda,
  error,
  className,
  children,
  ...resto
}: Envoltura & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <Envolver id={id} etiqueta={etiqueta} ayuda={ayuda} error={error}>
      <select id={id} className={clsx(BASE_CONTROL, 'pr-8', className)} {...resto}>
        {children}
      </select>
    </Envolver>
  )
}
