import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import { Toggle } from '@/components/ui/toggle'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Download,
  Italic,
  Mail,
  Plus,
  Settings,
  Underline,
} from 'lucide-react'

export function ButtonSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Button
      </h2>
      <div className="flex flex-wrap gap-3">
        <Button variant="default">Default</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Destructive</Button>
        <Button variant="link">Link</Button>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button>
          <Mail data-icon="inline-start" />
          Email
        </Button>
        <Button variant="outline">
          <Settings data-icon="inline-start" />
          Settings
        </Button>
        <Button variant="secondary">
          <Download data-icon="inline-start" />
          Download
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="xs">Extra Small</Button>
        <Button size="sm">Small</Button>
        <Button size="default">Default</Button>
        <Button size="lg">Large</Button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button size="icon-xs">
          <Plus />
        </Button>
        <Button size="icon-sm">
          <Plus />
        </Button>
        <Button size="icon">
          <Plus />
        </Button>
        <Button size="icon-lg">
          <Plus />
        </Button>
      </div>
    </section>
  )
}

export function ButtonGroupSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Button Group
      </h2>
      <div className="flex flex-col gap-4">
        <ButtonGroup>
          <Button variant="outline">Left</Button>
          <Button variant="outline">Center</Button>
          <Button variant="outline">Right</Button>
        </ButtonGroup>
        <ButtonGroup>
          <Button variant="outline" size="icon">
            <Bold />
          </Button>
          <Button variant="outline" size="icon">
            <Italic />
          </Button>
          <Button variant="outline" size="icon">
            <Underline />
          </Button>
        </ButtonGroup>
      </div>
    </section>
  )
}

export function ToggleSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Toggle
      </h2>
      <div className="flex flex-wrap gap-2">
        <Toggle aria-label="Toggle bold">
          <Bold />
        </Toggle>
        <Toggle aria-label="Toggle italic">
          <Italic />
        </Toggle>
        <Toggle aria-label="Toggle underline">
          <Underline />
        </Toggle>
        <Toggle variant="outline" aria-label="Toggle outline">
          <Bold />
        </Toggle>
      </div>
    </section>
  )
}

export function ToggleGroupSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Toggle Group
      </h2>
      <div className="flex flex-col gap-4">
        <ToggleGroup>
          <ToggleGroupItem value="bold" aria-label="Toggle bold">
            <Bold />
          </ToggleGroupItem>
          <ToggleGroupItem value="italic" aria-label="Toggle italic">
            <Italic />
          </ToggleGroupItem>
          <ToggleGroupItem value="underline" aria-label="Toggle underline">
            <Underline />
          </ToggleGroupItem>
        </ToggleGroup>
        <ToggleGroup variant="outline">
          <ToggleGroupItem value="left" aria-label="Align left">
            <AlignLeft />
          </ToggleGroupItem>
          <ToggleGroupItem value="center" aria-label="Align center">
            <AlignCenter />
          </ToggleGroupItem>
          <ToggleGroupItem value="right" aria-label="Align right">
            <AlignRight />
          </ToggleGroupItem>
        </ToggleGroup>
      </div>
    </section>
  )
}
