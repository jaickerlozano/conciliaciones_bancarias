import { LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { Logo } from '../componentes/Marco'
import { Boton } from '../componentes/ui/Boton'
import { Entrada } from '../componentes/ui/Campos'
import { useSesion } from '../sesion/contexto'

export function Ingresar() {
  const { usuario, ingresar } = useSesion()
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const destino = (ubicacion.state as { desde?: string } | null)?.desde ?? '/comunidades'

  if (usuario) return <Navigate to={destino} replace />

  const enviar = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const datos = new FormData(e.currentTarget)
    setEnviando(true)
    setError('')
    try {
      await ingresar(String(datos.get('usuario')), String(datos.get('clave')))
      navegar(destino, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo ingresar.')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-12 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Logo />
          <h1 className="mt-10 text-2xl font-semibold tracking-tight text-slate-900">Ingresar</h1>
          <p className="mt-1 text-sm text-slate-500">Use su usuario y clave de Gaudi.</p>
          <form onSubmit={enviar} className="mt-8 space-y-4">
            <Entrada etiqueta="Usuario" name="usuario" autoComplete="username" required autoFocus />
            <Entrada
              etiqueta="Clave"
              name="clave"
              type="password"
              autoComplete="current-password"
              required
            />
            {error && (
              <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </p>
            )}
            <Boton type="submit" icono={LogIn} cargando={enviando} className="w-full">
              Ingresar
            </Boton>
          </form>
        </div>
      </div>
      <div className="relative hidden overflow-hidden bg-marca-800 lg:block">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.12),transparent_55%)]" />
        <div className="relative flex h-full flex-col justify-end p-12 text-marca-50">
          <p className="max-w-md text-2xl font-medium leading-snug">
            Conciliaciones bancarias mensuales de cada comunidad, en minutos.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-marca-100/90">
            <li>· Sube las planillas de ingresos y egresos y la cartola del banco.</li>
            <li>· El sistema cruza cheques y depósitos y arrastra los pendientes.</li>
            <li>· Revisas lo dudoso, cierras el mes y descargas el informe.</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
