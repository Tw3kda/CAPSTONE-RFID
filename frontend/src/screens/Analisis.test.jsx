// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createApi } from '../api.js'
import { SessionProvider } from '../session.jsx'
import App from '../App.jsx'

afterEach(cleanup)

it('genera recomendación IA por solicitud explícita, reabre sin llamar y permite regenerar tras error', async () => {
  window.location.hash = '/analisis'
  let generations = 0
  const asset = { id: 4, nombre: 'Equipo en revisión', codigo: 'ACT-004', categoria_id: 1, categoria: 'Medición', estado: 'en_revision', condicion: 'Revisión pendiente', ultima_revision_at: null, ubicacion: { posicion_id: 1, espacio: 'Lab', gabinete: 'A', estante: '1', codigo: 'P1' } }
  const client = createApi({ storage: null, fetcher: async (url, options) => {
    let body
    if (url.endsWith('/auth/login')) body = { usuario: { id: 1, nombre: 'Usuario de prueba', rol: 'usuario', activo: true }, tokens: { access_token: 'test', refresh_token: 'test-refresh', token_type: 'bearer', expires_in: 900 } }
    else if (url.endsWith('/auth/me')) body = client.getSession().usuario
    else if (url.endsWith('/analisis/resumen')) body = { disponibles: 0, prestados: 0, en_revision: 1, uso_semanal: [{ semana: '2026-11-16', movimientos: 0 }], baja_utilizacion: [] }
    else if (url.endsWith('/analisis/reutilizables')) body = []
    else if (url.endsWith('/analisis/recomendacion')) {
      generations++
      if (generations === 2) return new Response(JSON.stringify({ detail: 'Provider temporarily unavailable' }), { status: 503 })
      body = { texto: 'Revisa el equipo antes de reemplazarlo.\n\nPrograma su mantenimiento.', activos_relacionados: [4], datos_insuficientes: true }
    } else if (url.includes('/activos')) body = url.endsWith('/4') ? asset : [asset]
    else throw new Error(`Unexpected request ${url} ${options.method || 'GET'}`)
    return new Response(JSON.stringify(body), { status: 200 })
  } })
  await client.login('id', 'test-only')
  class Socket { close() {} }
  render(<SessionProvider client={client} Socket={Socket}><App /></SessionProvider>)
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: 'Uso responsable de recursos' })
  expect(generations).toBe(0)
  await user.click(screen.getByRole('button', { name: 'Generar recomendación' }))
  await screen.findByText('Programa su mantenimiento.')
  await screen.findByRole('link', { name: 'Equipo en revisión' })
  await user.click(screen.getByRole('button', { name: 'Ocultar recomendación' }))
  expect(screen.queryByText('Programa su mantenimiento.')).toBeNull()
  expect(screen.getByRole('button', { name: 'Generar nueva recomendación' })).toBeTruthy()
  await user.click(screen.getByRole('button', { name: 'Mostrar recomendación' }))
  await screen.findByText('Programa su mantenimiento.')
  expect(generations).toBe(1)
  await user.click(screen.getByRole('button', { name: 'Generar nueva recomendación' }))
  await screen.findByRole('alert')
  expect(generations).toBe(2)
  await user.click(screen.getByRole('button', { name: 'Reintentar generación' }))
  await screen.findByText('Programa su mantenimiento.')
  expect(generations).toBe(3)
})
