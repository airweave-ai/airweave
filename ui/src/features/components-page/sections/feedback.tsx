import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { AlertCircle, Info } from 'lucide-react'

export function AlertSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Alert
      </h2>
      <div className="space-y-3 max-w-md">
        <Alert>
          <Info className="size-4" />
          <AlertTitle>Heads up!</AlertTitle>
          <AlertDescription>
            You can add components to your app using the CLI.
          </AlertDescription>
        </Alert>
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            Your session has expired. Please log in again.
          </AlertDescription>
        </Alert>
      </div>
    </section>
  )
}

export function ProgressSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Progress
      </h2>
      <div className="flex flex-col gap-4 max-w-md">
        <Progress value={25} />
        <Progress value={50} />
        <Progress value={75} />
      </div>
    </section>
  )
}

export function SkeletonSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Skeleton
      </h2>
      <div className="flex items-center gap-4">
        <Skeleton className="size-12 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-[250px]" />
          <Skeleton className="h-4 w-[200px]" />
        </div>
      </div>
    </section>
  )
}

export function SpinnerSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Spinner
      </h2>
      <div className="flex items-center gap-4">
        <Spinner className="size-4" />
        <Spinner className="size-6" />
        <Spinner className="size-8" />
      </div>
    </section>
  )
}
