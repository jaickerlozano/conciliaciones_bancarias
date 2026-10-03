import { useQuery, useQueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'

import { api, ErrorApi } from '../api/cliente'
import type { Usuario } from '../api/tipos'
import { Cargando } from '../componentes/ui/Estados'

import { ContextoSesion, useSesion, type ValorSesion } from './contexto'

async function obtenerUsuario(): Promise<Usuario | null> {
  await api<void>('/auth/csrf/') // asegura la cookie csrftoken antes de cualquier POST
  try {
    return await api<Usuario>('/auth/yo/')
  } catch (e) {
    if (e instanceof ErrorApi && e.estado === 403) return null
    throw e
  }
}

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { data, isPending } = useQuery({
    queryKey: ['sesion'],
    queryFn: obtenerUsuario,
    staleTime: Infinity,
    retry: false,
  })

  if (isPending) return <Cargando texto="Iniciando…" pantallaCompleta />

  const valor: ValorSesion = {
    usuario: data ?? null,
    ingresar: async (usuario, clave) => {
      const yo = await api<Usuario>('/auth/login/', { method: 'POST', json: { usuario, clave } })
      qc.setQueryData(['sesion'], yo)
    },
    salir: async () => {
      await api<void>('/auth/logout/', { method: 'POST' })
      qc.clear()
      qc.setQueryData(['sesion'], null)
    },
  }
  return <ContextoSesion value={valor}>{children}</ContextoSesion>
}

/** Redirige al login si no hay sesión, recordando a dónde quería ir. */
export function RequiereSesion({ children }: { children: ReactNode }) {
  const { usuario } = useSesion()
  const ubicacion = useLocation()
  if (!usuario) return <Navigate to="/ingresar" replace state={{ desde: ubicacion.pathname }} />
  return children
}
