import {
  Avatar,
  AvatarFallback,
  AvatarGroup,
  AvatarImage,
} from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Calendar } from '@/components/ui/calendar'
import { Card, CardContent } from '@/components/ui/card'
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from '@/components/ui/carousel'
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from '@/components/ui/empty'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Inbox, Mail } from 'lucide-react'

export function AvatarSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Avatar
      </h2>
      <div className="flex flex-wrap items-center gap-4">
        <Avatar size="sm">
          <AvatarImage src="https://github.com/shadcn.png" />
          <AvatarFallback>CN</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarImage src="https://github.com/shadcn.png" />
          <AvatarFallback>CN</AvatarFallback>
        </Avatar>
        <Avatar size="lg">
          <AvatarImage src="https://github.com/shadcn.png" />
          <AvatarFallback>CN</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
      </div>
      <AvatarGroup>
        <Avatar>
          <AvatarImage src="https://github.com/shadcn.png" />
          <AvatarFallback>CN</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarFallback>AB</AvatarFallback>
        </Avatar>
        <Avatar>
          <AvatarFallback>CD</AvatarFallback>
        </Avatar>
      </AvatarGroup>
    </section>
  )
}

export function BadgeSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Badge
      </h2>
      <div className="flex flex-wrap gap-3">
        <Badge>Default</Badge>
        <Badge variant="secondary">Secondary</Badge>
        <Badge variant="outline">Outline</Badge>
        <Badge variant="destructive">Destructive</Badge>
      </div>
    </section>
  )
}

export function CalendarSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Calendar
      </h2>
      <Calendar mode="single" className="rounded-lg border" />
    </section>
  )
}

export function CarouselSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Carousel
      </h2>
      <Carousel className="w-full max-w-xs mx-auto">
        <CarouselContent>
          {Array.from({ length: 5 }).map((_, index) => (
            <CarouselItem key={index}>
              <div className="p-1">
                <Card>
                  <CardContent className="flex aspect-square items-center justify-center p-6">
                    <span className="text-4xl font-semibold">{index + 1}</span>
                  </CardContent>
                </Card>
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
        <CarouselPrevious />
        <CarouselNext />
      </Carousel>
    </section>
  )
}

export function EmptySection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Empty
      </h2>
      <Empty className="border max-w-md">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Inbox className="size-4" />
          </EmptyMedia>
          <EmptyTitle>No messages</EmptyTitle>
          <EmptyDescription>
            You don't have any messages yet. Start a conversation!
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button size="sm">
            <Mail className="mr-2 size-4" />
            Compose
          </Button>
        </EmptyContent>
      </Empty>
    </section>
  )
}

export function TableSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Table
      </h2>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Invoice</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Method</TableHead>
            <TableHead className="text-right">Amount</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>INV001</TableCell>
            <TableCell>Paid</TableCell>
            <TableCell>Credit Card</TableCell>
            <TableCell className="text-right">$250.00</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>INV002</TableCell>
            <TableCell>Pending</TableCell>
            <TableCell>PayPal</TableCell>
            <TableCell className="text-right">$150.00</TableCell>
          </TableRow>
          <TableRow>
            <TableCell>INV003</TableCell>
            <TableCell>Unpaid</TableCell>
            <TableCell>Bank Transfer</TableCell>
            <TableCell className="text-right">$350.00</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </section>
  )
}
