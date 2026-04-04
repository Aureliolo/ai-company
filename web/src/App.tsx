import { CSPProvider } from '@base-ui/react/csp-provider'
import { MotionConfig } from 'framer-motion'
import { AppRouter } from '@/router'
import { getCspNonce } from '@/lib/csp'

const nonce = getCspNonce()

export default function App() {
  return (
    <CSPProvider nonce={nonce}>
      <MotionConfig nonce={nonce}>
        <AppRouter />
      </MotionConfig>
    </CSPProvider>
  )
}
