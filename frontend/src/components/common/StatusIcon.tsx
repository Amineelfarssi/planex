import { CheckCircle, Circle, AlertCircle, Loader, Square, SquareCheck } from 'lucide-react'

const icons = {
  pending: <Square className="w-4 h-4 text-planex-dimmed" />,
  in_progress: <Loader className="w-4 h-4 text-yellow-500 animate-spin" />,
  completed: <SquareCheck className="w-4 h-4 text-green-500" />,
  failed: <AlertCircle className="w-4 h-4 text-red-500" />,
}

export function StatusIcon({ status }: { status: string }) {
  return icons[status as keyof typeof icons] || icons.pending
}
