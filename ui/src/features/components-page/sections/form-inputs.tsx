import { Checkbox } from '@/components/ui/checkbox'
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from '@/components/ui/combobox'
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from '@/components/ui/input-group'
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from '@/components/ui/input-otp'
import { Kbd } from '@/components/ui/kbd'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Mail, Search } from 'lucide-react'

const frameworks = [
  { value: 'next.js', label: 'Next.js' },
  { value: 'sveltekit', label: 'SvelteKit' },
  { value: 'nuxt.js', label: 'Nuxt.js' },
  { value: 'remix', label: 'Remix' },
  { value: 'astro', label: 'Astro' },
]

export function InputSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Input
      </h2>
      <div className="flex flex-col gap-3 max-w-sm">
        <Input type="text" placeholder="Text input" />
        <Input type="email" placeholder="Email input" />
        <Input type="password" placeholder="Password input" />
        <Input type="text" placeholder="Disabled" disabled />
      </div>
    </section>
  )
}

export function InputGroupSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Input Group
      </h2>
      <div className="flex flex-col gap-3 max-w-sm">
        <InputGroup>
          <InputGroupAddon>
            <Mail className="size-4" />
          </InputGroupAddon>
          <InputGroupInput placeholder="Email address" />
        </InputGroup>
        <InputGroup>
          <InputGroupAddon>
            <Search className="size-4" />
          </InputGroupAddon>
          <InputGroupInput placeholder="Search..." />
          <InputGroupAddon align="inline-end">
            <Kbd>⌘K</Kbd>
          </InputGroupAddon>
        </InputGroup>
        <InputGroup>
          <InputGroupAddon>https://</InputGroupAddon>
          <InputGroupInput placeholder="example.com" />
        </InputGroup>
      </div>
    </section>
  )
}

export function InputOTPSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Input OTP
      </h2>
      <InputOTP maxLength={6}>
        <InputOTPGroup>
          <InputOTPSlot index={0} />
          <InputOTPSlot index={1} />
          <InputOTPSlot index={2} />
        </InputOTPGroup>
        <InputOTPSeparator />
        <InputOTPGroup>
          <InputOTPSlot index={3} />
          <InputOTPSlot index={4} />
          <InputOTPSlot index={5} />
        </InputOTPGroup>
      </InputOTP>
    </section>
  )
}

export function TextareaSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Textarea
      </h2>
      <div className="max-w-md">
        <Textarea placeholder="Type your message here..." />
      </div>
    </section>
  )
}

export function SelectSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Select
      </h2>
      <Select>
        <SelectTrigger className="w-[180px]">
          <SelectValue>Select a fruit</SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="apple">Apple</SelectItem>
          <SelectItem value="banana">Banana</SelectItem>
          <SelectItem value="orange">Orange</SelectItem>
          <SelectItem value="grape">Grape</SelectItem>
        </SelectContent>
      </Select>
    </section>
  )
}

export function ComboboxSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Combobox
      </h2>
      <Combobox>
        <ComboboxInput placeholder="Select framework..." className="w-[200px]" />
        <ComboboxContent>
          <ComboboxList>
            <ComboboxEmpty>No framework found.</ComboboxEmpty>
            {frameworks.map((framework) => (
              <ComboboxItem key={framework.value} value={framework.value}>
                {framework.label}
              </ComboboxItem>
            ))}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </section>
  )
}

export function CheckboxSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Checkbox
      </h2>
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <Checkbox id="terms" />
          <Label htmlFor="terms">Accept terms and conditions</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="newsletter" defaultChecked />
          <Label htmlFor="newsletter">Subscribe to newsletter</Label>
        </div>
        <div className="flex items-center gap-2">
          <Checkbox id="disabled" disabled />
          <Label htmlFor="disabled">Disabled option</Label>
        </div>
      </div>
    </section>
  )
}

export function RadioGroupSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Radio Group
      </h2>
      <RadioGroup defaultValue="option-1">
        <div className="flex items-center gap-2">
          <RadioGroupItem value="option-1" id="option-1" />
          <Label htmlFor="option-1">Option One</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="option-2" id="option-2" />
          <Label htmlFor="option-2">Option Two</Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="option-3" id="option-3" />
          <Label htmlFor="option-3">Option Three</Label>
        </div>
      </RadioGroup>
    </section>
  )
}

export function SwitchSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Switch
      </h2>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-2">
          <Switch id="airplane" />
          <Label htmlFor="airplane">Airplane Mode</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch id="notifications" defaultChecked />
          <Label htmlFor="notifications">Notifications</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch size="sm" id="compact" />
          <Label htmlFor="compact">Compact (small)</Label>
        </div>
      </div>
    </section>
  )
}

export function SliderSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Slider
      </h2>
      <div className="max-w-md">
        <Slider defaultValue={[50]} max={100} step={1} />
      </div>
    </section>
  )
}

export function FieldSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Field
      </h2>
      <FieldGroup className="max-w-sm">
        <Field>
          <FieldLabel htmlFor="field-name">Name</FieldLabel>
          <Input id="field-name" placeholder="Enter your name" />
          <FieldDescription>
            Your full name as it appears on your ID.
          </FieldDescription>
        </Field>
        <Field>
          <FieldLabel htmlFor="field-email">Email</FieldLabel>
          <Input
            id="field-email"
            type="email"
            placeholder="Enter your email"
          />
          <FieldError>Please enter a valid email address.</FieldError>
        </Field>
      </FieldGroup>
    </section>
  )
}

export function LabelSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Label
      </h2>
      <div className="flex flex-col gap-2 max-w-sm">
        <Label htmlFor="email-label">Email</Label>
        <Input id="email-label" type="email" placeholder="Enter email" />
      </div>
    </section>
  )
}

export function KbdSection() {
  return (
    <section className="space-y-4">
      <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
        Kbd
      </h2>
      <div className="flex flex-wrap gap-2">
        <Kbd>⌘</Kbd>
        <Kbd>K</Kbd>
        <Kbd>Ctrl</Kbd>
        <Kbd>Shift</Kbd>
        <Kbd>Enter</Kbd>
      </div>
    </section>
  )
}
