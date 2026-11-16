import { useContext, useEffect, useState } from 'react'
import { SessionContext } from './session-context.js'

export const useSession = () => useContext(SessionContext)

export function useApi(path) {
  const { client, revision } = useSession()
  const [state, setState] = useState({ data: null, error: null, key: null, path: null })
  const [retry, setRetry] = useState(0)
  const key = JSON.stringify([path, revision, retry])
  useEffect(() => {
    const controller = new AbortController()
    client.request(path, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) setState({ data, error: null, key, path })
    }).catch((error) => {
      if (!controller.signal.aborted) setState({ data: null, error, key, path })
    })
    return () => controller.abort()
  }, [path, client, key])
  return { data: state.path === path ? state.data : null, error: state.key === key ? state.error : null, loading: state.key !== key, reload: () => setRetry((value) => value + 1) }
}

export function useMutation() {
  const { client, invalidate } = useSession()
  const [state, setState] = useState({ busy: false, error: null })
  async function mutate(path, body, method = 'POST') {
    setState({ busy: true, error: null })
    try {
      const result = await client.request(path, { method, ...(body !== undefined ? { body } : {}) })
      setState({ busy: false, error: null })
      invalidate()
      return result
    } catch (error) { setState({ busy: false, error }); return undefined }
  }
  return { ...state, mutate, clearError: () => setState((value) => ({ ...value, error: null })) }
}
