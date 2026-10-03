import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { Toaster } from 'sonner'

import { ErrorApi } from './api/cliente'
import { Marco } from './componentes/Marco'
import { PaginaComunidad } from './paginas/Comunidad'
import { PaginaComunidades } from './paginas/Comunidades'
import { PaginaConciliacion } from './paginas/conciliacion/PaginaConciliacion'
import { Ingresar } from './paginas/Ingresar'
import { NoEncontrado } from './paginas/NoEncontrado'
import { ProveedorSesion, RequiereSesion } from './sesion/Sesion'

const clienteConsultas = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // no reintentar errores del cliente (404, permisos…)
      retry: (intentos, error) =>
        !(error instanceof ErrorApi && error.estado >= 400 && error.estado < 500) && intentos < 2,
    },
  },
})

const enrutador = createBrowserRouter([
  { path: '/ingresar', element: <Ingresar /> },
  {
    element: (
      <RequiereSesion>
        <Marco />
      </RequiereSesion>
    ),
    children: [
      { index: true, element: <Navigate to="/comunidades" replace /> },
      { path: 'comunidades', element: <PaginaComunidades /> },
      { path: 'comunidades/:id', element: <PaginaComunidad /> },
      { path: 'conciliaciones/:id', element: <PaginaConciliacion /> },
      { path: '*', element: <NoEncontrado /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={clienteConsultas}>
      <ProveedorSesion>
        <RouterProvider router={enrutador} />
      </ProveedorSesion>
      <Toaster position="bottom-right" richColors closeButton />
    </QueryClientProvider>
  </StrictMode>,
)
