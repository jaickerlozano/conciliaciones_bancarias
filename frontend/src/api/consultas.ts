// Hooks de datos. Cada mutación que devuelve el detalle de una conciliación lo guarda
// directo en la caché, así la pantalla se actualiza sin otra petición.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api, subir } from './cliente'
import type {
  AperturaManual,
  Archivo,
  Banco,
  Comunidad,
  Conciliacion,
  ConciliacionResumida,
  Cuenta,
  TipoArchivo,
} from './tipos'

export const claves = {
  comunidades: (filtro: FiltroComunidades) => ['comunidades', filtro] as const,
  comunidad: (id: number) => ['comunidad', id] as const,
  conciliacionesDeCuenta: (cuenta: number) => ['conciliaciones', { cuenta }] as const,
  conciliacion: (id: number) => ['conciliacion', id] as const,
  bancos: ['bancos'] as const,
}

export interface FiltroComunidades {
  q: string
  activa: 'true' | 'false' | ''
}

// ------------------------------------------------------------------ comunidades y cuentas

export function useComunidades(filtro: FiltroComunidades) {
  const params = new URLSearchParams()
  if (filtro.q.trim()) params.set('q', filtro.q.trim())
  if (filtro.activa) params.set('activa', filtro.activa)
  return useQuery({
    queryKey: claves.comunidades(filtro),
    queryFn: () => api<Comunidad[]>(`/comunidades/?${params}`),
    placeholderData: (previo) => previo,
  })
}

export function useComunidad(id: number) {
  return useQuery({
    queryKey: claves.comunidad(id),
    queryFn: () => api<Comunidad>(`/comunidades/${id}/`),
  })
}

export function useBancos() {
  return useQuery({
    queryKey: claves.bancos,
    queryFn: () => api<Banco[]>('/bancos/'),
    staleTime: Infinity,
  })
}

type DatosComunidad = Pick<Comunidad, 'nombre' | 'rut' | 'direccion' | 'activa'>

export function useGuardarComunidad() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...datos }: DatosComunidad & { id?: number }) =>
      id
        ? api<Comunidad>(`/comunidades/${id}/`, { method: 'PATCH', json: datos })
        : api<Comunidad>('/comunidades/', { method: 'POST', json: datos }),
    onSuccess: (comunidad) => {
      qc.setQueryData(claves.comunidad(comunidad.id), comunidad)
      void qc.invalidateQueries({ queryKey: ['comunidades'] })
    },
  })
}

type DatosCuenta = Pick<Cuenta, 'comunidad' | 'banco' | 'numero' | 'activa'>

export function useGuardarCuenta() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...datos }: DatosCuenta & { id?: number }) =>
      id
        ? api<Cuenta>(`/cuentas/${id}/`, { method: 'PATCH', json: datos })
        : api<Cuenta>('/cuentas/', { method: 'POST', json: datos }),
    onSuccess: (cuenta) => {
      void qc.invalidateQueries({ queryKey: claves.comunidad(cuenta.comunidad) })
      void qc.invalidateQueries({ queryKey: ['comunidades'] })
    },
  })
}

// ------------------------------------------------------------------ saldo inicial

export function leerHojas(archivo: File) {
  return subir<{ hojas: string[] }>('/cuentas/hojas/', { archivo })
}

function useAlCrearSaldoInicial() {
  const qc = useQueryClient()
  return (c: Conciliacion) => {
    qc.setQueryData(claves.conciliacion(c.id), c)
    void qc.invalidateQueries({ queryKey: claves.conciliacionesDeCuenta(c.cuenta) })
    void qc.invalidateQueries({ queryKey: claves.comunidad(c.comunidad_id) })
    void qc.invalidateQueries({ queryKey: ['comunidades'] })
  }
}

export function useImportarSaldoInicial(cuenta: number) {
  const alCrear = useAlCrearSaldoInicial()
  return useMutation({
    mutationFn: (datos: { archivo: File; hoja: string; periodo: string }) =>
      subir<Conciliacion>(`/cuentas/${cuenta}/apertura/`, datos),
    onSuccess: alCrear,
  })
}

export function useSaldoInicialManual(cuenta: number) {
  const alCrear = useAlCrearSaldoInicial()
  return useMutation({
    mutationFn: (datos: AperturaManual) =>
      api<Conciliacion>(`/cuentas/${cuenta}/apertura-manual/`, { method: 'POST', json: datos }),
    onSuccess: alCrear,
  })
}

// ------------------------------------------------------------------ conciliaciones

export function useConciliacionesDeCuenta(cuenta: number) {
  return useQuery({
    queryKey: claves.conciliacionesDeCuenta(cuenta),
    queryFn: () => api<ConciliacionResumida[]>(`/conciliaciones/?cuenta=${cuenta}`),
  })
}

export function useConciliacion(id: number) {
  return useQuery({
    queryKey: claves.conciliacion(id),
    queryFn: () => api<Conciliacion>(`/conciliaciones/${id}/`),
  })
}

function useActualizarCaches() {
  const qc = useQueryClient()
  return (c: Conciliacion) => {
    qc.setQueryData(claves.conciliacion(c.id), c)
    void qc.invalidateQueries({ queryKey: claves.conciliacionesDeCuenta(c.cuenta) })
    void qc.invalidateQueries({ queryKey: claves.comunidad(c.comunidad_id) })
    void qc.invalidateQueries({ queryKey: ['comunidades'] })
  }
}

export function useCrearConciliacion() {
  const actualizar = useActualizarCaches()
  return useMutation({
    mutationFn: (datos: { cuenta: number; periodo: string }) =>
      api<Conciliacion>('/conciliaciones/', { method: 'POST', json: datos }),
    onSuccess: actualizar,
  })
}

/** Acciones sobre una conciliación que devuelven su detalle actualizado. */
export function useAccionConciliacion(id: number) {
  const actualizar = useActualizarCaches()
  const qc = useQueryClient()
  const base = `/conciliaciones/${id}`
  const post = (ruta: string, json?: unknown) =>
    api<Conciliacion>(`${base}${ruta}`, { method: 'POST', json })

  const opciones = { onSuccess: actualizar }
  return {
    subirArchivo: useMutation({
      mutationFn: (d: { tipo: TipoArchivo; archivo: File }) =>
        subir<Archivo>(`${base}/archivos/`, d),
      onSuccess: () => qc.invalidateQueries({ queryKey: claves.conciliacion(id) }),
    }),
    procesar: useMutation({ mutationFn: () => post('/procesar/'), ...opciones }),
    confirmarCruce: useMutation({
      mutationFn: (cruce: number) => post(`/cruces/${cruce}/confirmar/`),
      ...opciones,
    }),
    confirmarTodos: useMutation({ mutationFn: () => post('/confirmar-todos/'), ...opciones }),
    deshacerCruce: useMutation({
      mutationFn: (cruce: number) =>
        api<Conciliacion>(`${base}/cruces/${cruce}/`, { method: 'DELETE' }),
      ...opciones,
    }),
    cruzarManual: useMutation({
      mutationFn: (d: { partida: number; movimiento: number }) => post('/cruces/', d),
      ...opciones,
    }),
    redondeo: useMutation({
      mutationFn: (monto: number) => post('/redondeo/', { monto }),
      ...opciones,
    }),
    cerrar: useMutation({ mutationFn: () => post('/cerrar/'), ...opciones }),
    reabrir: useMutation({
      mutationFn: (motivo: string) => post('/reabrir/', { motivo }),
      ...opciones,
    }),
    eliminar: useMutation({
      mutationFn: () => api<void>(`${base}/`, { method: 'DELETE' }),
      onSuccess: () => {
        qc.removeQueries({ queryKey: claves.conciliacion(id) })
        void qc.invalidateQueries({ queryKey: ['conciliaciones'] })
        void qc.invalidateQueries({ queryKey: ['comunidad'] })
        void qc.invalidateQueries({ queryKey: ['comunidades'] })
      },
    }),
  }
}
