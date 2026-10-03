import { screen } from '@testing-library/react'

import { conciliacionMayo, renderizar } from '../../test/fabricas'
import { Pasos } from './Pasos'
import { Resumen } from './Resumen'

describe('Resumen de la conciliación', () => {
  it('muestra el cálculo con la estructura del cliente y que cuadra', () => {
    renderizar(<Resumen c={conciliacionMayo()} />)
    expect(screen.getByText('Saldo conciliado Abril 2026')).toBeInTheDocument()
    expect(screen.getByText('$1.677.679')).toBeInTheDocument() // saldo según registro
    expect(screen.getByText('$6.131.348')).toBeInTheDocument() // cheques no cobrados
    expect(screen.getAllByText('$5.164.850')).toHaveLength(2) // conciliación = banco
    expect(screen.getByText('La conciliación cuadra')).toBeInTheDocument()
    expect(screen.getByText(/Quedan 7 cruces por revisar/)).toBeInTheDocument()
  })

  it('destaca la diferencia cuando no cuadra', () => {
    const c = conciliacionMayo()
    renderizar(<Resumen c={{ ...c, resumen: { ...c.resumen, diferencia: -50000 } }} />)
    expect(screen.getByText('Hay diferencia')).toBeInTheDocument()
    expect(screen.getByText('-$50.000')).toBeInTheDocument()
  })
})

describe('Pasos', () => {
  it('en borrador indica cuántos archivos faltan', () => {
    renderizar(
      <Pasos
        c={conciliacionMayo({
          estado: 'borrador',
          archivos: [
            {
              id: 1, tipo: 'ingresos', nombre_original: 'ingresos.xlsx', tamano: 1,
              sha256: '', subido_por: null, subido_en: '2026-06-01T00:00:00Z',
            },
          ],
        })}
      />,
    )
    expect(screen.getByText('1 de 3 cargados')).toBeInTheDocument()
  })

  it('procesada con cruces por revisar', () => {
    renderizar(<Pasos c={conciliacionMayo()} />)
    expect(screen.getByText('7 cruces por revisar')).toBeInTheDocument()
  })
})
