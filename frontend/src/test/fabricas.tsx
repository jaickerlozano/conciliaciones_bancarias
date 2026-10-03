import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'

import type { Conciliacion } from '../api/tipos'

export function renderizar(ui: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Mayo 2026 de Cinema, tal como lo devuelve la API después de procesar. */
export function conciliacionMayo(cambios: Partial<Conciliacion> = {}): Conciliacion {
  return {
    id: 7,
    cuenta: 1,
    cuenta_nombre: 'Comunidad Edificio Cinema — Santander 0-000-03-81745-8',
    cuenta_numero: '0-000-03-81745-8',
    banco_nombre: 'Santander',
    comunidad_id: 1,
    comunidad_nombre: 'Comunidad Edificio Cinema',
    anio: 2026,
    mes: 5,
    periodo: '2026-05',
    estado: 'procesada',
    creada_en: '2026-06-02T12:00:00Z',
    procesada_en: '2026-06-02T12:01:00Z',
    cerrada_en: null,
    resumen: {
      saldo_anterior: 2045773,
      total_ingresos: 6596118,
      total_egresos: 6964212,
      redondeo: 0,
      saldo_registro: 1677679,
      total_cheques_pendientes: 6131348,
      total_depositos_pendientes: 2644177,
      total_no_contabilizados: 0,
      saldo_conciliacion: 5164850,
      saldo_banco: 5164850,
      diferencia: 0,
      cruces_por_revisar: 7,
    },
    advertencias: [],
    cerrada_por: null,
    cheques_pendientes: [],
    depositos_pendientes: [],
    movimientos_no_contabilizados: [],
    movimientos_repetidos: [],
    cruces: [],
    archivos: [],
    eventos: [],
    ...cambios,
  }
}
