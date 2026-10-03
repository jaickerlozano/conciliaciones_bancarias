import {
  fecha,
  leerMonto,
  nombrePeriodo,
  periodoAnterior,
  periodoDeTexto,
  periodoSiguiente,
  pesos,
} from './formato'

describe('formatos chilenos', () => {
  it('pesos', () => {
    expect(pesos(1379448)).toBe('$1.379.448')
    expect(pesos(-66010)).toBe('-$66.010')
    expect(pesos(0)).toBe('$0')
    expect(pesos(null)).toBe('—')
  })

  it('fecha sin desfase de zona horaria', () => {
    expect(fecha('2026-05-26')).toBe('26/05/2026')
    expect(fecha('2026-05-01T03:00:00Z')).toBe('01/05/2026')
    expect(fecha(null)).toBe('—')
  })

  it('períodos', () => {
    expect(nombrePeriodo('2026-05')).toBe('Mayo 2026')
    expect(periodoSiguiente('2026-12')).toBe('2027-01')
    expect(periodoAnterior('2026-01')).toBe('2025-12')
  })

  it('deduce el período del nombre de una hoja', () => {
    expect(periodoDeTexto('ABRIL´26')).toBe('2026-04')
    expect(periodoDeTexto("DICIEMBRE'25")).toBe('2025-12')
    expect(periodoDeTexto('MAYO 2026')).toBe('2026-05')
    expect(periodoDeTexto('Hoja1')).toBeNull()
  })

  it('lee montos escritos de varias formas', () => {
    expect(leerMonto('1.379.448')).toBe(1379448)
    expect(leerMonto('$ 2.045.773')).toBe(2045773)
    expect(leerMonto('-4.414')).toBe(-4414)
    expect(leerMonto('abc')).toBeNull()
    expect(leerMonto('')).toBeNull()
  })
})
