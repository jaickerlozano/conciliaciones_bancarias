import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { conciliacionMayo, cruce, movimiento, partida, renderizar } from '../../test/fabricas'
import { Revision } from './Revision'

beforeAll(() => {
  // jsdom no implementa <dialog>
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})

const abono = movimiento({ id: 50, monto: 285796, descripcion: 'DEPOSITO BCI' })
const p1 = partida({ id: 1, comprobante: 34917, monto: 168465 })
const p2 = partida({ id: 2, comprobante: 34918, monto: 117331 })
const suelto = cruce(partida({ id: 3, comprobante: 40, monto: 5000 }), movimiento({ id: 51, monto: 5000 }))
const g1 = cruce(p1, abono, { id: 11, tipo: 'agrupado', grupo: 'G1' })
const g2 = cruce(p2, abono, { id: 12, tipo: 'agrupado', grupo: 'G1' })

describe('Revisión con cruces agrupados', () => {
  it('muestra un grupo como una sola tarjeta con el total de sus partidas', () => {
    renderizar(<Revision c={conciliacionMayo({ cruces: [g1, suelto, g2] })} />)
    expect(screen.getByRole('button', { name: 'Confirmar todos (2)' })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Confirmar' })).toHaveLength(2)

    const tarjeta = screen.getByText(/2 partidas · Grupo G1/).closest('li') as HTMLElement
    expect(within(tarjeta).getByText(/#34917/)).toBeInTheDocument()
    expect(within(tarjeta).getByText(/#34918/)).toBeInTheDocument()
    expect(within(tarjeta).getAllByText('$285.796')).toHaveLength(2) // total = movimiento
  })

  it('ofrece "Cruzar…" en un movimiento si hay partidas menores que podrían sumarlo', async () => {
    const usuario = userEvent.setup()
    renderizar(
      <Revision
        c={conciliacionMayo({
          depositos_pendientes: [p1, p2],
          movimientos_no_contabilizados: [abono],
        })}
      />,
    )
    await usuario.click(screen.getByRole('tab', { name: /No contabilizados/ }))
    expect(screen.getByRole('button', { name: 'Cruzar…' })).toBeInTheDocument()
  })
})
