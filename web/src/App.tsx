import { MotionConfig } from 'framer-motion'
import { AppRouter } from '@/router'
import { getCspNonce } from '@/lib/csp'

const nonce = getCspNonce()

export default function App() {
  return (
    <MotionConfig nonce={nonce}>
      <AppRouter />
    </MotionConfig>
  )
}
