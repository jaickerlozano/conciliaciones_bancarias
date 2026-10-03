import clsx from 'clsx'
import { CheckCircle2, FileSpreadsheet, PenLine, Plus, Trash2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'

import { leerHojas, useImportarSaldoInicial, useSaldoInicialManual } from '../api/consultas'
import type { AperturaManual, Conciliacion, Cuenta } from '../api/tipos'
import { Boton } from '../componentes/ui/Boton'
import { Entrada, Selector } from '../componentes/ui/Campos'
import { Modal } from '../componentes/ui/Modal'
import { leerMonto, nombrePeriodo, periodoDeTexto, periodoSiguiente, pesos } from '../lib/formato'

type Modo = 'manual' | 'importar'

export function SaldoInicial({
  abierto,
  alCerrar,
  cuenta,
}: {
  abierto: boolean
  alCerrar: () => void
  cuenta: Cuenta
}) {
  const [modo, setModo] = useState<Modo>('manual')
  const navegar = useNavigate()
  const alCrear = (c: Conciliacion) => {
    toast.success(
      `Saldo inicial de ${nombrePeriodo(c.periodo)} guardado. Ya puede iniciar ${nombrePeriodo(periodoSiguiente(c.periodo))}.`,
    )
    alCerrar()
    navegar(`/conciliaciones/${c.id}`)
  }

  return (
    <Modal
      abierto={abierto}
      alCerrar={alCerrar}
      ancho="xl"
      titulo="Saldo inicial de la cuenta"
      descripcion={`${cuenta.banco_nombre} ${cuenta.numero}. Corresponde al cierre del mes anterior al primero que conciliará en el sistema.`}
    >
      <div className="mb-5 grid gap-3 sm:grid-cols-2">
        {(
          [
            ['manual', PenLine, 'Ingresar a mano', 'Saldos y pendientes del último cierre. Recomendado para cuentas nuevas.'],
            ['importar', FileSpreadsheet, 'Importar desde planilla', 'Desde la hoja del último mes de la planilla “Conciliación mensual”.'],
          ] as const
        ).map(([valor, Icono, titulo, texto]) => (
          <button
            key={valor}
            type="button"
            onClick={() => setModo(valor)}
            aria-pressed={modo === valor}
            className={clsx(
              'flex gap-3 rounded-xl p-4 text-left ring-1 transition',
              modo === valor ? 'bg-marca-50 ring-2 ring-marca-600' : 'bg-white ring-slate-200 hover:ring-slate-300',
            )}
          >
            <Icono className={clsx('mt-0.5 size-5', modo === valor ? 'text-marca-700' : 'text-slate-400')} />
            <span>
              <span className="block text-sm font-semibold text-slate-900">{titulo}</span>
              <span className="block text-xs text-slate-500">{texto}</span>
            </span>
          </button>
        ))}
      </div>
      {modo === 'manual' ? (
        <FormularioManual cuenta={cuenta.id} alCrear={alCrear} alCancelar={alCerrar} />
      ) : (
        <FormularioImportar cuenta={cuenta.id} alCrear={alCrear} alCancelar={alCerrar} />
      )}
    </Modal>
  )
}

// ------------------------------------------------------------------ importar

function FormularioImportar({
  cuenta,
  alCrear,
  alCancelar,
}: {
  cuenta: number
  alCrear: (c: Conciliacion) => void
  alCancelar: () => void
}) {
  const importar = useImportarSaldoInicial(cuenta)
  const [archivo, setArchivo] = useState<File | null>(null)
  const [hojas, setHojas] = useState<string[]>([])
  const [hoja, setHoja] = useState('')
  const [periodo, setPeriodo] = useState('')
  const [leyendo, setLeyendo] = useState(false)

  const elegirArchivo = async (f: File | undefined) => {
    if (!f) return
    setArchivo(f)
    setLeyendo(true)
    try {
      const { hojas } = await leerHojas(f)
      setHojas(hojas)
      // sugerir la hoja del mes más reciente
      const conPeriodo = hojas
        .filter((h) => !h.includes('('))
        .map((h) => ({ h, p: periodoDeTexto(h) }))
        .filter((x): x is { h: string; p: string } => x.p !== null)
        .sort((a, b) => b.p.localeCompare(a.p))
      if (conPeriodo[0]) {
        setHoja(conPeriodo[0].h)
        setPeriodo(conPeriodo[0].p)
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'No se pudo leer la planilla.')
      setArchivo(null)
    } finally {
      setLeyendo(false)
    }
  }

  return (
    <div className="space-y-4">
      <Entrada
        etiqueta="Planilla de conciliación (.xlsx / .xlsm)"
        type="file"
        accept=".xlsx,.xlsm"
        onChange={(e) => elegirArchivo(e.target.files?.[0])}
        ayuda={leyendo ? 'Leyendo hojas…' : 'La misma planilla donde hacían la conciliación a mano.'}
      />
      {hojas.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          <Selector
            etiqueta="Hoja del último mes cerrado"
            value={hoja}
            onChange={(e) => {
              setHoja(e.target.value)
              const p = periodoDeTexto(e.target.value)
              if (p) setPeriodo(p)
            }}
          >
            <option value="" disabled>
              Elija una hoja
            </option>
            {[...hojas].reverse().map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </Selector>
          <Entrada
            etiqueta="Mes que representa"
            type="month"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
            ayuda={periodo && `El primer mes a conciliar será ${nombrePeriodo(periodoSiguiente(periodo))}.`}
          />
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
        <Boton variante="secundario" onClick={alCancelar}>
          Cancelar
        </Boton>
        <Boton
          disabled={!archivo || !hoja || !periodo}
          cargando={importar.isPending}
          onClick={() =>
            archivo &&
            importar.mutate(
              { archivo, hoja, periodo },
              { onSuccess: alCrear, onError: (e) => toast.error(e.message) },
            )
          }
        >
          Importar saldo inicial
        </Boton>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------ manual

interface Fila {
  clave: number
  comprobante: string
  fecha: string
  detalle: string // nº cheque, depto o descripción según la lista
  monto: string
}

const filaVacia = (): Fila => ({
  clave: Math.random(),
  comprobante: '',
  fecha: '',
  detalle: '',
  monto: '',
})

function sumar(filas: Fila[]): number {
  return filas.reduce((t, f) => t + (leerMonto(f.monto) ?? 0), 0)
}

function FormularioManual({
  cuenta,
  alCrear,
  alCancelar,
}: {
  cuenta: number
  alCrear: (c: Conciliacion) => void
  alCancelar: () => void
}) {
  const guardar = useSaldoInicialManual(cuenta)
  const [periodo, setPeriodo] = useState('')
  const [registro, setRegistro] = useState('')
  const [banco, setBanco] = useState('')
  const [cheques, setCheques] = useState<Fila[]>([])
  const [depositos, setDepositos] = useState<Fila[]>([])
  const [movimientos, setMovimientos] = useState<Fila[]>([])

  const saldoRegistro = leerMonto(registro)
  const saldoBanco = leerMonto(banco)
  const conciliacion =
    saldoRegistro === null ? null : saldoRegistro + sumar(cheques) - sumar(depositos) + sumar(movimientos)
  const diferencia = conciliacion === null || saldoBanco === null ? null : saldoBanco - conciliacion
  const filasInvalidas = [...cheques, ...depositos, ...movimientos].some((f) => leerMonto(f.monto) === null)
  const movSinFecha = movimientos.some((f) => !f.fecha)
  const listo = Boolean(periodo) && diferencia === 0 && !filasInvalidas && !movSinFecha

  const enviar = () => {
    const comp = (f: Fila) => (f.comprobante ? Number(f.comprobante) : null)
    const datos: AperturaManual = {
      periodo,
      saldo_registro: saldoRegistro!,
      saldo_banco: saldoBanco!,
      cheques_pendientes: cheques.map((f) => ({
        comprobante: comp(f), fecha: f.fecha || null, monto: leerMonto(f.monto)!, cheque: f.detalle,
      })),
      depositos_pendientes: depositos.map((f) => ({
        comprobante: comp(f), fecha: f.fecha || null, monto: leerMonto(f.monto)!, depto: f.detalle,
      })),
      movimientos_no_contabilizados: movimientos.map((f) => ({
        fecha: f.fecha, descripcion: f.detalle, monto: leerMonto(f.monto)!,
      })),
    }
    guardar.mutate(datos, { onSuccess: alCrear, onError: (e) => toast.error(e.message) })
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Entrada
          etiqueta="Mes del cierre"
          type="month"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
          ayuda={periodo ? `Se conciliará desde ${nombrePeriodo(periodoSiguiente(periodo))}.` : 'Ej.: el último mes conciliado a mano.'}
          required
        />
        <Entrada
          etiqueta="Saldo según registro"
          inputMode="numeric"
          placeholder="$0"
          value={registro}
          onChange={(e) => setRegistro(e.target.value)}
          error={registro && saldoRegistro === null ? 'Monto inválido' : undefined}
        />
        <Entrada
          etiqueta="Saldo según banco (cartola)"
          inputMode="numeric"
          placeholder="$0"
          value={banco}
          onChange={(e) => setBanco(e.target.value)}
          error={banco && saldoBanco === null ? 'Monto inválido' : undefined}
        />
      </div>

      <ListaEditable
        titulo="Cheques girados no cobrados"
        filas={cheques}
        setFilas={setCheques}
        etiquetaDetalle="Nº cheque"
      />
      <ListaEditable
        titulo="Depósitos contabilizados no registrados en banco"
        filas={depositos}
        setFilas={setDepositos}
        etiquetaDetalle="Depto"
      />
      <ListaEditable
        titulo="Movimientos no contabilizados"
        ayuda="Movimientos del banco que no están en las planillas. Abono positivo, cargo negativo (ej. -4.414)."
        filas={movimientos}
        setFilas={setMovimientos}
        etiquetaDetalle="Descripción"
        sinComprobante
        fechaObligatoria
      />

      <div
        className={clsx(
          'flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3 text-sm',
          diferencia === 0 ? 'bg-emerald-50 text-emerald-900' : 'bg-slate-100 text-slate-700',
        )}
      >
        <span className="flex items-center gap-2">
          {diferencia === 0 ? (
            <CheckCircle2 className="size-5 text-emerald-600" />
          ) : (
            <XCircle className="size-5 text-slate-400" />
          )}
          Saldo según conciliación <strong className="monto">{pesos(conciliacion)}</strong> · banco{' '}
          <strong className="monto">{pesos(saldoBanco)}</strong>
        </span>
        <span className="monto font-semibold">
          {diferencia === null ? 'Complete los saldos' : diferencia === 0 ? 'Cuadra' : `Diferencia ${pesos(diferencia)}`}
        </span>
      </div>

      <div className="flex justify-end gap-2 border-t border-slate-200 pt-4">
        <Boton variante="secundario" onClick={alCancelar}>
          Cancelar
        </Boton>
        <Boton disabled={!listo} cargando={guardar.isPending} onClick={enviar}>
          Guardar saldo inicial
        </Boton>
      </div>
    </div>
  )
}

function ListaEditable({
  titulo,
  ayuda,
  filas,
  setFilas,
  etiquetaDetalle,
  sinComprobante = false,
  fechaObligatoria = false,
}: {
  titulo: string
  ayuda?: string
  filas: Fila[]
  setFilas: (f: Fila[]) => void
  etiquetaDetalle: string
  sinComprobante?: boolean
  fechaObligatoria?: boolean
}) {
  const cambiar = (clave: number, campo: keyof Fila, valor: string) =>
    setFilas(filas.map((f) => (f.clave === clave ? { ...f, [campo]: valor } : f)))
  const celda =
    'w-full rounded-md border-0 px-2 py-1.5 text-sm ring-1 ring-slate-300 ring-inset focus:ring-2 focus:ring-marca-600 focus:outline-none'

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            {titulo} <span className="monto font-normal text-slate-500">· {pesos(sumar(filas))}</span>
          </h3>
          {ayuda && <p className="text-xs text-slate-500">{ayuda}</p>}
        </div>
        <Boton variante="secundario" tamano="sm" icono={Plus} onClick={() => setFilas([...filas, filaVacia()])}>
          Agregar
        </Boton>
      </div>
      {filas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-400">Ninguno.</p>
      ) : (
        <div className="space-y-2">
          {filas.map((f) => (
            <div key={f.clave} className="grid grid-cols-12 items-center gap-2">
              {!sinComprobante && (
                <input
                  className={clsx(celda, 'col-span-2')}
                  placeholder="Nº comp."
                  inputMode="numeric"
                  value={f.comprobante}
                  onChange={(e) => cambiar(f.clave, 'comprobante', e.target.value.replace(/\D/g, ''))}
                  aria-label="Nº comprobante"
                />
              )}
              <input
                className={clsx(celda, 'col-span-3', fechaObligatoria && !f.fecha && 'ring-amber-400')}
                type="date"
                value={f.fecha}
                onChange={(e) => cambiar(f.clave, 'fecha', e.target.value)}
                aria-label="Fecha"
              />
              <input
                className={clsx(celda, sinComprobante ? 'col-span-5' : 'col-span-3')}
                placeholder={etiquetaDetalle}
                value={f.detalle}
                onChange={(e) => cambiar(f.clave, 'detalle', e.target.value)}
                aria-label={etiquetaDetalle}
              />
              <input
                className={clsx(celda, 'monto col-span-3 text-right', f.monto && leerMonto(f.monto) === null && 'ring-rose-400')}
                placeholder="Monto"
                inputMode="numeric"
                value={f.monto}
                onChange={(e) => cambiar(f.clave, 'monto', e.target.value)}
                aria-label="Monto"
              />
              <button
                type="button"
                onClick={() => setFilas(filas.filter((x) => x.clave !== f.clave))}
                className="col-span-1 justify-self-center rounded-md p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                aria-label="Quitar fila"
              >
                <Trash2 className="size-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
