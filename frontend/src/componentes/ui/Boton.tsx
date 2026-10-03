import clsx from 'clsx'
import { Loader2, type LucideIcon } from 'lucide-react'
import type { ButtonHTMLAttributes } from 'react'

type Variante = 'primario' | 'secundario' | 'fantasma' | 'peligro' | 'exito'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-marca-700 text-white hover:bg-marca-800 shadow-sm',
  secundario: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 shadow-sm',
  fantasma: 'text-slate-600 hover:bg-slate-100 hover:text-slate-900',
  peligro: 'bg-rose-600 text-white hover:bg-rose-700 shadow-sm',
  exito: 'bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm',
}

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante
  tamano?: 'sm' | 'md'
  icono?: LucideIcon
  cargando?: boolean
}

export function Boton({
  variante = 'primario',
  tamano = 'md',
  icono: Icono,
  cargando = false,
  disabled,
  className,
  children,
  type = 'button',
  ...resto
}: Props) {
  return (
    <button
      type={type}
      disabled={disabled || cargando}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors',
        'disabled:cursor-not-allowed disabled:opacity-50',
        tamano === 'sm' ? 'px-2.5 py-1.5 text-xs' : 'px-3.5 py-2 text-sm',
        VARIANTES[variante],
        className,
      )}
      {...resto}
    >
      {cargando ? (
        <Loader2 className="size-4 animate-spin" aria-hidden />
      ) : (
        Icono && <Icono className={tamano === 'sm' ? 'size-3.5' : 'size-4'} aria-hidden />
      )}
      {children}
    </button>
  )
}
