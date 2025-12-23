import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { AspectRatio } from '@/components/ui/aspect-ratio'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemMedia,
  ItemTitle,
} from '@/components/ui/item'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { ChevronsUpDown, FileText } from 'lucide-react'
import * as React from 'react'

export function AccordionSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Accordion
      </h2>
      <Accordion className="w-full max-w-md">
        <AccordionItem value="item-1">
          <AccordionTrigger>Is it accessible?</AccordionTrigger>
          <AccordionContent>
            Yes. It adheres to the WAI-ARIA design pattern.
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-2">
          <AccordionTrigger>Is it styled?</AccordionTrigger>
          <AccordionContent>
            Yes. It comes with default styles that match your design system.
          </AccordionContent>
        </AccordionItem>
        <AccordionItem value="item-3">
          <AccordionTrigger>Is it animated?</AccordionTrigger>
          <AccordionContent>
            Yes. It's animated by default with smooth transitions.
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </section>
  )
}

export function AspectRatioSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Aspect Ratio
      </h2>
      <div className="w-[300px]">
        <AspectRatio ratio={16 / 9} className="bg-muted rounded-lg">
          <img
            src="https://images.unsplash.com/photo-1588345921523-c2dcdb7f1dcd?w=800&dpr=2&q=80"
            alt="Photo"
            className="rounded-lg object-cover w-full h-full"
          />
        </AspectRatio>
      </div>
    </section>
  )
}

export function CardSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Card
      </h2>
      <div className="grid md:grid-cols-2 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>Card description goes here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Card content with some example text.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>With Footer</CardTitle>
            <CardDescription>This card has a footer.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Some content here.</p>
          </CardContent>
          <CardFooter>
            <Button size="sm">Action</Button>
          </CardFooter>
        </Card>
      </div>
    </section>
  )
}

export function CollapsibleSection() {
  const [isCollapsibleOpen, setIsCollapsibleOpen] = React.useState(false)

  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Collapsible
      </h2>
      <Collapsible
        open={isCollapsibleOpen}
        onOpenChange={setIsCollapsibleOpen}
        className="w-[350px] space-y-2"
      >
        <div className="flex items-center justify-between space-x-4">
          <h4 className="text-sm font-medium">
            @peduarte starred 3 repositories
          </h4>
          <CollapsibleTrigger render={<Button variant="ghost" size="sm" />}>
            <ChevronsUpDown className="size-4" />
            <span className="sr-only">Toggle</span>
          </CollapsibleTrigger>
        </div>
        <div className="rounded-md border px-4 py-2 text-sm">
          @radix-ui/primitives
        </div>
        <CollapsibleContent className="space-y-2">
          <div className="rounded-md border px-4 py-2 text-sm">
            @radix-ui/colors
          </div>
          <div className="rounded-md border px-4 py-2 text-sm">
            @stitches/react
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  )
}

export function ItemSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Item
      </h2>
      <ItemGroup className="max-w-md">
        <Item variant="outline">
          <ItemMedia variant="icon">
            <FileText className="size-4" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>Document.pdf</ItemTitle>
            <ItemDescription>2.4 MB • Updated 2 days ago</ItemDescription>
          </ItemContent>
        </Item>
        <Item variant="outline">
          <ItemMedia variant="icon">
            <FileText className="size-4" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>Presentation.pptx</ItemTitle>
            <ItemDescription>5.1 MB • Updated yesterday</ItemDescription>
          </ItemContent>
        </Item>
        <Item variant="outline">
          <ItemMedia variant="icon">
            <FileText className="size-4" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>Spreadsheet.xlsx</ItemTitle>
            <ItemDescription>1.2 MB • Updated today</ItemDescription>
          </ItemContent>
        </Item>
      </ItemGroup>
    </section>
  )
}

export function ResizableSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Resizable
      </h2>
      <ResizablePanelGroup
        direction="horizontal"
        className="max-w-md rounded-lg border"
      >
        <ResizablePanel defaultSize={50}>
          <div className="flex h-[100px] items-center justify-center p-6">
            <span className="font-medium">One</span>
          </div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={50}>
          <div className="flex h-[100px] items-center justify-center p-6">
            <span className="font-medium">Two</span>
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </section>
  )
}

export function ScrollAreaSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Scroll Area
      </h2>
      <ScrollArea className="h-[200px] w-[350px] rounded-md border p-4">
        <div className="space-y-4">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="text-sm">
              Item {i + 1} - Scrollable content
            </div>
          ))}
        </div>
      </ScrollArea>
    </section>
  )
}

export function SeparatorSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Separator
      </h2>
      <div className="max-w-md">
        <div className="space-y-1">
          <h4 className="text-sm font-medium">Radix Primitives</h4>
          <p className="text-sm text-muted-foreground">
            An open-source UI component library.
          </p>
        </div>
        <Separator className="my-4" />
        <div className="flex h-5 items-center gap-4 text-sm">
          <div>Blog</div>
          <Separator orientation="vertical" />
          <div>Docs</div>
          <Separator orientation="vertical" />
          <div>Source</div>
        </div>
      </div>
    </section>
  )
}
