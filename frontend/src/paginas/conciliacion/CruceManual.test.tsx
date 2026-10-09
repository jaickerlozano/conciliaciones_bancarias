import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { conciliacionMayo, movimiento, partida, renderizar } from '../../test/fabricas'
import { CruceManual } from './CruceManual'

beforeAll(() => {
  // jsdom no implementa <dialog>
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// depósito BCI de $285.796 = ingresos #34917 + #34918
const abono = movimiento({ id: 50, monto: 285796, fecha: '2026-06-03', descripcion: 'DEPOSITO' })
const p1 = partida({ id: 1, comprobante: 34917, monto: 168465, fecha: '2026-05-30' })
const p2 = partida({ id: 2, comprobante: 34918, monto: 117331, fecha: '2026-05-31' })
const p3 = partida({ id: 3, comprobante: 34919, monto: 50000, fecha: '2026-05-02' })
const mayor = partida({ id: 4, comprobante: 34920, monto: 300000, fecha: '2026-06-03' })
const egreso = partida({ id: 5, tipo: 'EGRESO', comprobante: 900, monto: 100000 })

function conciliacion() {
  return conciliacionMayo({
    depositos_pendientes: [p3, p1, mayor, p2],
    cheques_pendientes: [egreso],
    movimientos_no_contabilizados: [abono],
  })
}

function simularApi() {
  const fetch = vi.fn(
    async () =>
      new Response(JSON.stringify(conciliacion()), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
  )
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('Cruce manual agrupado desde un movimiento', () => {
  it('solo ofrece partidas compatibles de monto menor o igual al movimiento', () => {
    renderizar(<CruceManual c={conciliacion()} origen={{ movimiento: abono }} alCerrar={() => {}} />)
    expect(screen.getByLabelText(/#34917/)).toBeInTheDocument()
    expect(screen.getByLabelText(/#34918/)).toBeInTheDocument()
    expect(screen.getByLabelText(/#34919/)).toBeInTheDocument()
    expect(screen.queryByLabelText(/#34920/)).not.toBeInTheDocument() // mayor que el abono
    expect(screen.queryByLabelText(/#900/)).not.toBeInTheDocument() // egreso: no es compatible
  })

  it('habilita "Cruzar" solo cuando la suma seleccionada es igual al monto', async () => {
    const usuario = userEvent.setup()
    renderizar(<CruceManual c={conciliacion()} origen={{ movimiento: abono }} alCerrar={() => {}} />)
    const cruzar = screen.getByRole('button', { name: 'Cruzar seleccionadas' })
    expect(cruzar).toBeDisabled()

    await usuario.click(screen.getByLabelText(/#34917/))
    await usuario.click(screen.getByLabelText(/#34919/))
    expect(screen.getByText(/Seleccionado \$218\.465 de \$285\.796/)).toBeInTheDocument()
    expect(screen.getByText('Faltan $67.331')).toBeInTheDocument()
    expect(cruzar).toBeDisabled()

    await usuario.click(screen.getByLabelText(/#34919/))
    await usuario.click(screen.getByLabelText(/#34918/))
    expect(screen.getByText('Cuadra')).toBeInTheDocument()
    expect(cruzar).toBeEnabled()
  })

  it('envía las partidas y el movimiento y cierra al terminar', async () => {
    const usuario = userEvent.setup()
    const fetch = simularApi()
    const alCerrar = vi.fn()
    renderizar(<CruceManual c={conciliacion()} origen={{ movimiento: abono }} alCerrar={alCerrar} />)

    await usuario.click(screen.getByLabelText(/#34917/))
    await usuario.click(screen.getByLabelText(/#34918/))
    await usuario.click(screen.getByRole('button', { name: 'Cruzar seleccionadas' }))

    expect(fetch).toHaveBeenCalledTimes(1)
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/conciliaciones/7/cruces/')
    const cuerpo = JSON.parse(init.body as string) as { partidas: number[]; movimiento: number }
    expect(cuerpo.movimiento).toBe(50)
    expect([...cuerpo.partidas].sort()).toEqual([1, 2]) // el orden no importa al servidor
    await vi.waitFor(() => expect(alCerrar).toHaveBeenCalled())
  })

  it('muestra un estado vacío útil si no hay partidas compatibles', () => {
    renderizar(
      <CruceManual
        c={conciliacionMayo({ movimientos_no_contabilizados: [abono] })}
        origen={{ movimiento: abono }}
        alCerrar={() => {}}
      />,
    )
    expect(screen.getByText('Sin candidatos')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cruzar seleccionadas' })).not.toBeInTheDocument()
  })
})

describe('Cruce manual desde una partida', () => {
  it('mantiene el cruce 1:1 por el mismo monto', async () => {
    const usuario = userEvent.setup()
    const fetch = simularApi()
    const igual = movimiento({ id: 60, monto: 168465 })
    renderizar(
      <CruceManual
        c={conciliacionMayo({ movimientos_no_contabilizados: [abono, igual] })}
        origen={{ partida: p1 }}
        alCerrar={() => {}}
      />,
    )
    const botones = screen.getAllByRole('button', { name: 'Cruzar' })
    expect(botones).toHaveLength(1)
    await usuario.click(botones[0])
    const [, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(JSON.parse(init.body as string)).toEqual({ partidas: [1], movimiento: 60 })
  })
})
