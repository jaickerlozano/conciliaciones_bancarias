import clsx from 'clsx'
import { X } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  abierto: boolean
  alCerrar: () => void
  titulo: string
  descripcion?: ReactNode
  children: ReactNode
  pie?: ReactNode
  ancho?: 'md' | 'lg' | 'xl'
}

/** Modal accesible sobre <dialog> nativo (foco atrapado, Esc para cerrar). */
export function Modal({ abierto, alCerrar, titulo, descripcion, children, pie, ancho = 'md' }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialogo = ref.current
    if (!dialogo) return
    if (abierto && !dialogo.open) dialogo.showModal()
    if (!abierto && dialogo.open) dialogo.close()
  }, [abierto])

  return (
    <dialog
      ref={ref}
      onClose={alCerrar}
      onClick={(e) => e.target === ref.current && alCerrar()}
      className={clsx(
        'm-auto w-[calc(100%-2rem)] rounded-2xl bg-white p-0 shadow-xl backdrop:bg-slate-900/40',
        { md: 'max-w-lg', lg: 'max-w-2xl', xl: 'max-w-4xl' }[ancho],
      )}
    >
      {abierto && (
        <div className="flex max-h-[85vh] flex-col">
          <header className="flex items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-slate-900">{titulo}</h2>
              {descripcion && <p className="mt-1 text-sm text-slate-500">{descripcion}</p>}
            </div>
            <button
              type="button"
              onClick={alCerrar}
              className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
              aria-label="Cerrar"
            >
              <X className="size-5" />
            </button>
          </header>
          <div className="overflow-y-auto px-6 py-5">{children}</div>
          {pie && (
            <footer className="flex justify-end gap-2 border-t border-slate-200 bg-slate-50 px-6 py-3">
              {pie}
            </footer>
          )}
        </div>
      )}
    </dialog>
  )
}
