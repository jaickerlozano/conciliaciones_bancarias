import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { Cuenta } from '../api/tipos'
import { renderizar } from '../test/fabricas'
import { SaldoInicial } from './SaldoInicial'

const cuenta: Cuenta = {
  id: 1,
  comunidad: 1,
  comunidad_nombre: 'Edificio Prueba',
  banco: 'santander',
  banco_nombre: 'Santander',
  numero: '123',
  activa: true,
  ultima_conciliacion: null,
}

beforeAll(() => {
  // jsdom no implementa <dialog>
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true
  }
  HTMLDialogElement.prototype.close = function () {
    this.open = false
  }
})

describe('Saldo inicial manual', () => {
  it('solo permite guardar cuando cuadra', async () => {
    const usuario = userEvent.setup()
    renderizar(<SaldoInicial abierto alCerrar={() => {}} cuenta={cuenta} />)
    const guardar = screen.getByRole('button', { name: 'Guardar saldo inicial' })

    await usuario.type(screen.getByLabelText('Mes del cierre'), '2026-04')
    await usuario.type(screen.getByLabelText('Saldo según registro'), '1.000.000')
    await usuario.type(screen.getByLabelText('Saldo según banco (cartola)'), '1.080.000')
    expect(screen.getByText('Diferencia $80.000')).toBeInTheDocument()
    expect(guardar).toBeDisabled()

    // un cheque girado no cobrado de $80.000 explica la diferencia
    await usuario.click(screen.getAllByRole('button', { name: 'Agregar' })[0])
    await usuario.type(screen.getByLabelText('Monto'), '80.000')
    expect(screen.getByText('Cuadra')).toBeInTheDocument()
    expect(guardar).toBeEnabled()
  })
})
