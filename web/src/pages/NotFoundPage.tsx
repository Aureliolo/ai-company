import { Link } from 'react-router'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <h1 className="text-4xl font-bold text-text-primary">404</h1>
      <p className="text-text-secondary">Page not found</p>
      <Button variant="outline" asChild>
        <Link to="/">Back to Dashboard</Link>
      </Button>
    </div>
  )
}
