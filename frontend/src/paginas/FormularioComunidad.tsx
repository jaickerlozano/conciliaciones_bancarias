import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ErrorApi } from '../api/cliente'
import { useGuardarComunidad } from '../api/consultas'
import type { Comunidad } from '../api/tipos'
import { Boton } from '../componentes/ui/Boton'
import { Entrada } from '../componentes/ui/Campos'
import { Modal } from '../componentes/ui/Modal'

export function FormularioComunidad({
  abierto,
  alCerrar,
  comunidad,
  alGuardar,
}: {
  abierto: boolean
  alCerrar: () => void
  comunidad?: Comunidad
  alGuardar?: (c: Comunidad) => void
}) {
  const guardar = useGuardarComunidad()
  const [errores, setErrores] = useState<Record<string, string[]>>({})

  const enviar = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const d = new FormData(e.currentTarget)
    setErrores({})
    guardar.mutate(
      {
        id: comunidad?.id,
        nombre: String(d.get('nombre')).trim(),
        rut: String(d.get('rut')).trim(),
        direccion: String(d.get('direccion')).trim(),
        activa: d.get('activa') === 'on',
      },
      {
        onSuccess: (c) => {
          toast.success(comunidad ? 'Comunidad actualizada' : 'Comunidad creada')
          alGuardar?.(c)
          alCerrar()
        },
        onError: (err) => {
          if (err instanceof ErrorApi && Object.keys(err.campos).length) setErrores(err.campos)
          else toast.error(err.message)
        },
      },
    )
  }

  return (
    <Modal
      abierto={abierto}
      alCerrar={alCerrar}
      titulo={comunidad ? 'Editar comunidad' : 'Nueva comunidad'}
      pie={
        <>
          <Boton variante="secundario" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" form="form-comunidad" cargando={guardar.isPending}>
            Guardar
          </Boton>
        </>
      }
    >
      <form id="form-comunidad" onSubmit={enviar} className="space-y-4">
        <Entrada
          etiqueta="Nombre"
          name="nombre"
          defaultValue={comunidad?.nombre}
          placeholder="Comunidad Edificio …"
          required
          autoFocus
          error={errores.nombre?.[0]}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Entrada
            etiqueta="RUT"
            name="rut"
            defaultValue={comunidad?.rut}
            placeholder="56.039.860-3"
            error={errores.rut?.[0]}
          />
          <Entrada
            etiqueta="Dirección"
            name="direccion"
            defaultValue={comunidad?.direccion}
            error={errores.direccion?.[0]}
          />
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            name="activa"
            defaultChecked={comunidad?.activa ?? true}
            className="size-4 rounded border-slate-300 text-marca-600 focus:ring-marca-600"
          />
          Comunidad activa (las inactivas se ocultan del listado por defecto)
        </label>
      </form>
    </Modal>
  )
}
