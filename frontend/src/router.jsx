import { useSyncExternalStore } from 'react'

// Hash routes also work when the frontend is served as static files.
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

