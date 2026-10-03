// Tipos de la API (espejo de los serializers de Django). Montos: enteros en pesos.

export type EstadoConciliacion = 'importada' | 'borrador' | 'procesada' | 'cerrada'
export type TipoArchivo = 'ingresos' | 'egresos' | 'cartola' | 'apertura'
export type TipoCruce = 'cheque' | 'monto_fecha' | 'sugerido' | 'manual'

export interface Usuario {
  id: number
  usuario: string
  nombre: string
  es_admin: boolean
}

export interface Banco {
  valor: string
  nombre: string
}

export interface ResumenUltimo {
  id: number
  periodo: string
  estado: EstadoConciliacion
}

export interface Cuenta {
  id: number
  comunidad: number
  comunidad_nombre: string
  banco: string
  banco_nombre: string
  numero: string
  activa: boolean
  ultima_conciliacion: ResumenUltimo | null
}

export interface Comunidad {
  id: number
  nombre: string
  rut: string
  direccion: string
  activa: boolean
  cuentas: Cuenta[]
}

export interface Resumen {
  saldo_anterior: number
  total_ingresos: number
  total_egresos: number
  redondeo: number
  saldo_registro: number
  total_cheques_pendientes: number
  total_depositos_pendientes: number
  total_no_contabilizados: number
  saldo_conciliacion: number
  saldo_banco: number | null
  diferencia: number | null
  cruces_por_revisar: number
}

export interface ConciliacionResumida {
  id: number
  cuenta: number
  cuenta_nombre: string
  cuenta_numero: string
  banco_nombre: string
  comunidad_id: number
  comunidad_nombre: string
  anio: number
  mes: number
  periodo: string
  estado: EstadoConciliacion
  creada_en: string
  procesada_en: string | null
  cerrada_en: string | null
  resumen: Resumen
}

export interface Partida {
  id: number
  tipo: 'INGRESO' | 'EGRESO'
  origen: 'periodo' | 'arrastre'
  comprobante: number | null
  fecha: string | null
  monto: number
  glosa: string
  depto: string
  cheque: string
}

export interface Movimiento {
  id: number
  origen: 'periodo' | 'arrastre' | 'repetido'
  fecha: string
  descripcion: string
  monto: number
  es_cargo: boolean
  documento: string
  sucursal: string
}

export interface Cruce {
  id: number
  tipo: TipoCruce
  nota: string
  confirmado: boolean
  confirmado_por: string | null
  confirmado_en: string | null
  requiere_revision: boolean
  partida: Partida
  movimiento: Movimiento
}

export interface Archivo {
  id: number
  tipo: TipoArchivo
  nombre_original: string
  tamano: number
  sha256: string
  subido_por: string | null
  subido_en: string
}

export interface Evento {
  id: number
  accion: string
  detalle: string
  usuario: string | null
  fecha: string
}

export interface Conciliacion extends ConciliacionResumida {
  advertencias: string[]
  cerrada_por: string | null
  cheques_pendientes: Partida[]
  depositos_pendientes: Partida[]
  movimientos_no_contabilizados: Movimiento[]
  movimientos_repetidos: Movimiento[]
  cruces: Cruce[]
  archivos: Archivo[]
  eventos: Evento[]
}

export interface AperturaManual {
  periodo: string
  saldo_registro: number
  saldo_banco: number
  cheques_pendientes: {
    comprobante?: number | null
    fecha?: string | null
    monto: number
    glosa?: string
    cheque?: string
  }[]
  depositos_pendientes: {
    comprobante?: number | null
    fecha?: string | null
    monto: number
    depto?: string
    glosa?: string
  }[]
  movimientos_no_contabilizados: { fecha: string; descripcion?: string; monto: number }[]
}
