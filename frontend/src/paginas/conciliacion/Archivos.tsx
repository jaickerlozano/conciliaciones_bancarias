import { Download, Play } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { useAccionConciliacion } from '../../api/consultas'
import type { Conciliacion, TipoArchivo } from '../../api/tipos'
import { Boton } from '../../componentes/ui/Boton'
import { Modal } from '../../componentes/ui/Modal'
import { Tarjeta } from '../../componentes/ui/Tarjeta'
import { ZonaArchivo } from '../../componentes/ui/ZonaArchivo'
import { fechaHora, nombrePeriodo, tamanoArchivo } from '../../lib/formato'

const ZONAS: { tipo: TipoArchivo; titulo: string; descripcion: string; aceptar: string }[] = [
  {
    tipo: 'ingresos',
    titulo: 'Planilla de ingresos',
    descripcion: 'Listado acumulado (.xlsx/.xlsm). Se toma el bloque del mes.',
    aceptar: '.xlsx,.xlsm',
  },
  {
    tipo: 'egresos',
    titulo: 'Planilla de egresos',
    descripcion: 'Listado acumulado (.xlsx/.xlsm). Se toma el bloque del mes.',
    aceptar: '.xlsx,.xlsm',
  },
  {
    tipo: 'cartola',
    titulo: 'Cartola del banco',
    descripcion: 'PDF oficial del banco o plantilla estándar (.xlsx).',
    aceptar: '.pdf,.xlsx,.xls,.csv',
  },
]

export function Archivos({ c, compacto = false }: { c: Conciliacion; compacto?: boolean }) {
  const acciones = useAccionConciliacion(c.id)
  const [subiendo, setSubiendo] = useState<TipoArchivo | null>(null)
  const [reemplazo, setReemplazo] = useState<{ tipo: TipoArchivo; archivo: File } | null>(null)
  const editable = c.estado === 'borrador' || c.estado === 'procesada'
  const porTipo = Object.fromEntries(c.archivos.map((a) => [a.tipo, a]))
  const completos = ZONAS.every((z) => porTipo[z.tipo])

  const subir = (tipo: TipoArchivo, archivo: File) => {
    setSubiendo(tipo)
    acciones.subirArchivo.mutate(
      { tipo, archivo },
      {
        onSuccess: () => toast.success(`${archivo.name} cargado`),
        onError: (e) => toast.error(e.message),
        onSettled: () => setSubiendo(null),
      },
    )
  }

  // en una conciliación ya procesada, reemplazar un archivo borra los resultados: confirmar
  const alElegir = (tipo: TipoArchivo, archivo: File) =>
    c.estado === 'procesada' ? setReemplazo({ tipo, archivo }) : subir(tipo, archivo)

  const procesar = () =>
    acciones.procesar.mutate(undefined, {
      onSuccess: (r) =>
        r.resumen.diferencia === 0
          ? toast.success(
              `Procesada: cuadra. ${r.resumen.cruces_por_revisar} cruces por revisar.`,
            )
          : toast.warning(`Procesada con diferencia. Revise los pendientes.`),
      onError: (e) => toast.error(e.message, { duration: 10000 }),
    })

  return (
    <Tarjeta
      titulo={compacto ? 'Archivos del mes' : `Paso 1 · Suba los archivos de ${nombrePeriodo(c.periodo)}`}
      subtitulo={
        compacto
          ? undefined
          : 'Las planillas completas: el sistema toma automáticamente el bloque “CIERRE MES” correspondiente.'
      }
      acciones={
        <>
          <a
            href="/api/plantilla-cartola/"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-marca-700"
            title="Para bancos o formatos que el sistema aún no lee"
          >
            <Download className="size-3.5" aria-hidden />
            Plantilla estándar de cartola
          </a>
          {c.estado === 'borrador' && (
            <Boton icono={Play} disabled={!completos} cargando={acciones.procesar.isPending} onClick={procesar}>
              Procesar conciliación
            </Boton>
          )}
        </>
      }
    >
      <div className="grid gap-4 md:grid-cols-3">
        {ZONAS.map((z) => {
          const actual = porTipo[z.tipo]
          return (
            <ZonaArchivo
              key={z.tipo}
              titulo={z.titulo}
              descripcion={z.descripcion}
              aceptar={z.aceptar}
              deshabilitado={!editable}
              subiendo={subiendo === z.tipo}
              archivoActual={
                actual && {
                  nombre: actual.nombre_original,
                  detalle: `${tamanoArchivo(actual.tamano)} · ${fechaHora(actual.subido_en)}${actual.subido_por ? ` · ${actual.subido_por}` : ''}`,
                }
              }
              alElegir={(archivo) => alElegir(z.tipo, archivo)}
            />
          )
        })}
      </div>
      {acciones.procesar.isPending && (
        <p className="mt-4 text-sm text-slate-500">
          Leyendo planillas y cartola y cruzando movimientos… puede tardar unos segundos.
        </p>
      )}

      <Modal
        abierto={reemplazo !== null}
        alCerrar={() => setReemplazo(null)}
        titulo="¿Reemplazar el archivo?"
        pie={
          <>
            <Boton variante="secundario" onClick={() => setReemplazo(null)}>
              Cancelar
            </Boton>
            <Boton
              variante="peligro"
              onClick={() => {
                if (reemplazo) subir(reemplazo.tipo, reemplazo.archivo)
                setReemplazo(null)
              }}
            >
              Reemplazar y volver a procesar
            </Boton>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          La conciliación ya está procesada. Al cambiar un archivo se borran los resultados y las
          confirmaciones de cruces, y habrá que procesarla de nuevo.
        </p>
      </Modal>
    </Tarjeta>
  )
}
