import { useState, type FormEvent } from 'react'
import { toast } from 'sonner'

import { ErrorApi } from '../api/cliente'
import { useBancos, useGuardarCuenta } from '../api/consultas'
import type { Cuenta } from '../api/tipos'
import { Boton } from '../componentes/ui/Boton'
import { Entrada, Selector } from '../componentes/ui/Campos'
import { Modal } from '../componentes/ui/Modal'

export function FormularioCuenta({
  abierto,
  alCerrar,
  comunidad,
  cuenta,
}: {
  abierto: boolean
  alCerrar: () => void
  comunidad: number
  cuenta?: Cuenta
}) {
  const { data: bancos = [] } = useBancos()
  const guardar = useGuardarCuenta()
  const [errores, setErrores] = useState<Record<string, string[]>>({})

  const enviar = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const d = new FormData(e.currentTarget)
    setErrores({})
    guardar.mutate(
      {
        id: cuenta?.id,
        comunidad,
        banco: String(d.get('banco')),
        numero: String(d.get('numero')).trim(),
        activa: d.get('activa') === 'on',
      },
      {
        onSuccess: () => {
          toast.success(cuenta ? 'Cuenta actualizada' : 'Cuenta agregada')
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
      titulo={cuenta ? 'Editar cuenta' : 'Agregar cuenta bancaria'}
      descripcion="El banco y el número deben coincidir con los de la cartola; el sistema lo verifica al procesar."
      pie={
        <>
          <Boton variante="secundario" onClick={alCerrar}>
            Cancelar
          </Boton>
          <Boton type="submit" form="form-cuenta" cargando={guardar.isPending}>
            Guardar
          </Boton>
        </>
      }
    >
      <form id="form-cuenta" onSubmit={enviar} className="space-y-4">
        <Selector
          etiqueta="Banco"
          name="banco"
          defaultValue={cuenta?.banco ?? 'santander'}
          error={errores.banco?.[0]}
        >
          {bancos.map((b) => (
            <option key={b.valor} value={b.valor}>
              {b.nombre}
            </option>
          ))}
        </Selector>
        <Entrada
          etiqueta="Número de cuenta"
          name="numero"
          defaultValue={cuenta?.numero}
          placeholder="0-000-03-81745-8"
          required
          error={errores.numero?.[0] ?? errores.non_field_errors?.[0]}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            name="activa"
            defaultChecked={cuenta?.activa ?? true}
            className="size-4 rounded border-slate-300 text-marca-600 focus:ring-marca-600"
          />
          Cuenta activa
        </label>
      </form>
    </Modal>
  )
}
