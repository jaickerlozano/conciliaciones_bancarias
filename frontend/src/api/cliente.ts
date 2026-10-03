// Cliente HTTP: sesión por cookie (mismo origen vía proxy) + token CSRF en métodos que escriben.

export class ErrorApi extends Error {
  readonly estado: number
  readonly campos: Record<string, string[]>

  constructor(estado: number, mensaje: string, campos: Record<string, string[]> = {}) {
    super(mensaje)
    this.estado = estado
    this.campos = campos
  }
}

function leerCookie(nombre: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((c) => c.startsWith(`${nombre}=`))
    ?.split('=')[1]
}

/** Convierte la respuesta de error de DRF en un mensaje legible. */
function mensajeDeError(estado: number, cuerpo: unknown): ErrorApi {
  if (cuerpo && typeof cuerpo === 'object') {
    const datos = cuerpo as Record<string, unknown>
    if (typeof datos.detail === 'string') return new ErrorApi(estado, datos.detail)
    const campos: Record<string, string[]> = {}
    for (const [campo, valor] of Object.entries(datos)) {
      campos[campo] = Array.isArray(valor) ? valor.map(String) : [String(valor)]
    }
    const primero = Object.entries(campos)[0]
    if (primero) {
      const [campo, errores] = primero
      const prefijo = campo === 'non_field_errors' ? '' : `${campo}: `
      return new ErrorApi(estado, `${prefijo}${errores[0]}`, campos)
    }
  }
  if (estado === 403) return new ErrorApi(estado, 'Su sesión expiró. Vuelva a ingresar.')
  if (estado === 404) return new ErrorApi(estado, 'No se encontró lo que busca.')
  return new ErrorApi(estado, 'Ocurrió un error en el servidor. Intente nuevamente.')
}

export async function api<T>(ruta: string, opciones: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...resto } = opciones
  const metodo = (resto.method ?? 'GET').toUpperCase()
  const cabeceras = new Headers(headers)
  cabeceras.set('Accept', 'application/json')
  if (json !== undefined) cabeceras.set('Content-Type', 'application/json')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(metodo)) {
    const token = leerCookie('csrftoken')
    if (token) cabeceras.set('X-CSRFToken', token)
  }

  let respuesta: Response
  try {
    respuesta = await fetch(`/api${ruta}`, {
      ...resto,
      method: metodo,
      headers: cabeceras,
      credentials: 'same-origin',
      body: json !== undefined ? JSON.stringify(json) : resto.body,
    })
  } catch {
    throw new ErrorApi(0, 'No hay conexión con el servidor.')
  }

  if (respuesta.status === 204) return undefined as T
  const tipo = respuesta.headers.get('Content-Type') ?? ''
  const cuerpo = tipo.includes('application/json') ? await respuesta.json() : null
  if (!respuesta.ok) throw mensajeDeError(respuesta.status, cuerpo)
  return cuerpo as T
}

export function subir<T>(ruta: string, campos: Record<string, string | Blob>): Promise<T> {
  const formulario = new FormData()
  for (const [k, v] of Object.entries(campos)) formulario.append(k, v)
  return api<T>(ruta, { method: 'POST', body: formulario })
}
