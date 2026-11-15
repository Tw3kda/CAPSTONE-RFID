import { useEffect, useState, useSyncExternalStore } from 'react'

// Navegación mínima por hash (#/ruta) para no depender de una librería todavía.
const suscribir = (cb) => {
  window.addEventListener('hashchange', cb)
  return () => window.removeEventListener('hashchange', cb)
}
const leerHash = () => window.location.hash.slice(1) || '/acceso'

export function useRoute() {
  const hash = useSyncExternalStore(suscribir, leerHash)
  const [path, qs = ''] = hash.split('?')
  return { path, query: new URLSearchParams(qs) }
}

export const navigate = (to) => {
  window.location.hash = to
}

export function Link({ to, children, ...rest }) {
  return (
    <a href={`#${to}`} {...rest}>
      {children}
    </a>
  )
}

// Simula un evento físico (lectura QR o RFID): avanza solo tras `ms`.
// Se pausa mientras el puntero o el foco están sobre el elemento que recibe estas props.
export function useAutoAdvance(to, ms = 1800) {
  const [pausado, setPausado] = useState(false)
  useEffect(() => {
    if (pausado) return
    const t = setTimeout(() => navigate(to), ms)
    return () => clearTimeout(t)
  }, [to, ms, pausado])
  return {
    onMouseEnter: () => setPausado(true),
    onMouseLeave: () => setPausado(false),
    onFocus: () => setPausado(true),
    onBlur: () => setPausado(false),
  }
}
