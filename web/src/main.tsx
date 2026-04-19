import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { ensureFreshAppState } from './utils/app-version'
import './styles/global.css'

// Gate boot on the build-id check so a stale csrf_token / session cookie
// from an older version is cleared before any React code (or API call)
// observes it. On mismatch this triggers a logout + storage wipe +
// reload; on match or first load it resolves immediately.
await ensureFreshAppState()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
