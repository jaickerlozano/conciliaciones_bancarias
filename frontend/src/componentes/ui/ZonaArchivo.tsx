import clsx from 'clsx'
import { CheckCircle2, FileUp, Loader2 } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'

interface Props {
  titulo: string
  descripcion: ReactNode
  aceptar: string // ej. ".xlsx,.xlsm"
  archivoActual?: { nombre: string; detalle: string } | null
  subiendo?: boolean
  deshabilitado?: boolean
  alElegir: (archivo: File) => void
}

/** Tarjeta para arrastrar o elegir un archivo. Muestra el archivo ya cargado, si lo hay. */
export function ZonaArchivo({
  titulo,
  descripcion,
  aceptar,
  archivoActual,
  subiendo = false,
  deshabilitado = false,
  alElegir,
}: Props) {
  const entrada = useRef<HTMLInputElement>(null)
  const [encima, setEncima] = useState(false)
  const cargado = Boolean(archivoActual)

  const elegir = (archivos: FileList | null) => {
    const archivo = archivos?.[0]
    if (archivo) alElegir(archivo)
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault()
        if (!deshabilitado) setEncima(true)
      }}
      onDragLeave={() => setEncima(false)}
      onDrop={(e) => {
        e.preventDefault()
        setEncima(false)
        if (!deshabilitado) elegir(e.dataTransfer.files)
      }}
      className={clsx(
        'relative flex flex-col rounded-xl border-2 border-dashed p-4 transition-colors',
        encima && 'border-marca-500 bg-marca-50',
        !encima && cargado && 'border-emerald-300 bg-emerald-50/40',
        !encima && !cargado && 'border-slate-300 bg-white',
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'rounded-lg p-2',
            cargado ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500',
          )}
        >
          {subiendo ? (
            <Loader2 className="size-5 animate-spin" aria-hidden />
          ) : cargado ? (
            <CheckCircle2 className="size-5" aria-hidden />
          ) : (
            <FileUp className="size-5" aria-hidden />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold text-slate-900">{titulo}</h3>
          <p className="text-xs text-slate-500">{descripcion}</p>
        </div>
      </div>

      {archivoActual && (
        <div className="mt-3 rounded-lg bg-white px-3 py-2 text-xs ring-1 ring-emerald-200">
          <p className="truncate font-medium text-slate-800" title={archivoActual.nombre}>
            {archivoActual.nombre}
          </p>
          <p className="text-slate-500">{archivoActual.detalle}</p>
        </div>
      )}

      <button
        type="button"
        disabled={deshabilitado || subiendo}
        onClick={() => entrada.current?.click()}
        className="mt-3 text-left text-sm font-medium text-marca-700 hover:text-marca-900 disabled:cursor-not-allowed disabled:text-slate-400"
      >
        {subiendo ? 'Subiendo…' : cargado ? 'Reemplazar archivo' : 'Elegir archivo o arrastrarlo aquí'}
      </button>
      <input
        ref={entrada}
        type="file"
        accept={aceptar}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => {
          elegir(e.target.files)
          e.target.value = ''
        }}
      />
    </div>
  )
}
