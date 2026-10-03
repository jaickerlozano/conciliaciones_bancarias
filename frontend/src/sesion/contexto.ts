import { createContext, use } from 'react'

import type { Usuario } from '../api/tipos'

export interface ValorSesion {
  usuario: Usuario | null
  ingresar: (usuario: string, clave: string) => Promise<void>
  salir: () => Promise<void>
}

export const ContextoSesion = createContext<ValorSesion | null>(null)

export function useSesion(): ValorSesion {
  const valor = use(ContextoSesion)
  if (!valor) throw new Error('useSesion debe usarse dentro de ProveedorSesion')
  return valor
}
