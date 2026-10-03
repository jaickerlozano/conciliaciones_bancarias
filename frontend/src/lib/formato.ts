// Formatos chilenos: $1.379.448, 26/05/2026, "Mayo 2026".

const MESES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

export function pesos(monto: number | null | undefined): string {
  if (monto === null || monto === undefined) return '—'
  const signo = monto < 0 ? '-' : ''
  return `${signo}$${Math.abs(monto).toLocaleString('es-CL')}`
}

/** "2026-05-26" o ISO con hora -> "26/05/2026" (sin desfase de zona horaria). */
export function fecha(valor: string | null | undefined): string {
  if (!valor) return '—'
  const [a, m, d] = valor.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

export function fechaHora(valor: string | null | undefined): string {
  if (!valor) return '—'
  const d = new Date(valor)
  const dos = (n: number) => String(n).padStart(2, '0')
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`
}

/** "2026-05" -> "Mayo 2026" */
export function nombrePeriodo(periodo: string): string {
  const [anio, mes] = periodo.split('-').map(Number)
  return `${MESES[mes - 1]} ${anio}`
}

export function periodoSiguiente(periodo: string): string {
  const [anio, mes] = periodo.split('-').map(Number)
  return mes === 12 ? `${anio + 1}-01` : `${anio}-${String(mes + 1).padStart(2, '0')}`
}

export function periodoAnterior(periodo: string): string {
  const [anio, mes] = periodo.split('-').map(Number)
  return mes === 1 ? `${anio - 1}-12` : `${anio}-${String(mes - 1).padStart(2, '0')}`
}

/** Intenta deducir el período de un nombre de hoja: "ABRIL´26", "MAYO 2026" -> "2026-04". */
export function periodoDeTexto(texto: string): string | null {
  const limpio = texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase()
  const indice = MESES.findIndex((m) => limpio.includes(m.toUpperCase()))
  const anio = limpio.match(/(\d{4}|\d{2})(?!\d)/)
  if (indice < 0 || !anio) return null
  const numero = Number(anio[1])
  return `${numero < 100 ? 2000 + numero : numero}-${String(indice + 1).padStart(2, '0')}`
}

/** "1.379.448", "$ 1379448", "-66.010" -> número; null si no es un monto válido. */
export function leerMonto(texto: string): number | null {
  const limpio = texto.replace(/[$\s.]/g, '').replace(',', '.')
  if (!/^-?\d+(\.\d+)?$/.test(limpio)) return null
  return Math.round(Number(limpio))
}

export function tamanoArchivo(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
