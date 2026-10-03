import { SearchX } from 'lucide-react'
import { Link } from 'react-router'

import { Vacio } from '../componentes/ui/Estados'

export function NoEncontrado() {
  return (
    <Vacio
      icono={SearchX}
      titulo="Página no encontrada"
      accion={
        <Link to="/comunidades" className="text-sm font-medium text-marca-700 hover:underline">
          Volver a comunidades
        </Link>
      }
    >
      La dirección no existe o fue eliminada.
    </Vacio>
  )
}
