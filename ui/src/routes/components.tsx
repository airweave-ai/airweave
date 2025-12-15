import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { AspectRatio } from '@/components/ui/aspect-ratio'
import {
  Avatar,
  AvatarFallback,
  AvatarGroup,
  AvatarImage,
} from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { ButtonGroup } from '@/components/ui/button-group'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from '@/components/ui/context-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from '@/components/ui/drawer'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'
import { Input } from '@/components/ui/input'
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSeparator,
  InputOTPSlot,
} from '@/components/ui/input-otp'
import { Kbd } from '@/components/ui/kbd'
import { Label } from '@/components/ui/label'
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Progress } from '@/components/ui/progress'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Separator } from '@/components/ui/separator'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Slider } from '@/components/ui/slider'
import { Spinner } from '@/components/ui/spinner'
import { Switch } from '@/components/ui/switch'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { Toggle } from '@/components/ui/toggle'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { createFileRoute } from '@tanstack/react-router'
import {
  AlertCircle,
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  ChevronsUpDown,
  Download,
  Info,
  Italic,
  Mail,
  Plus,
  Search,
  Settings,
  Underline,
} from 'lucide-react'
import * as React from 'react'

export const Route = createFileRoute('/components')({
  component: ComponentsPage,
})

function ComponentsPage() {
  const [isCollapsibleOpen, setIsCollapsibleOpen] = React.useState(false)

  return (
    <div className="min-h-screen bg-background/80 backdrop-blur-sm p-12">
      <div className="mx-auto max-w-4xl space-y-12">
        {/* Button */}
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

        {/* Accordion */}
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

        {/* Alert */}
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

        {/* Alert Dialog */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Alert Dialog
          </h2>
          <AlertDialog>
            <AlertDialogTrigger render={<Button variant="outline" />}>
              Open Alert Dialog
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                <AlertDialogDescription>
                  This action cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction>Continue</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </section>

        {/* Aspect Ratio */}
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

        {/* Avatar */}
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

        {/* Badge */}
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

        {/* Breadcrumb */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Breadcrumb
          </h2>
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <BreadcrumbLink href="#">Home</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbLink href="#">Components</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage>Breadcrumb</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </section>

        {/* Button Group */}
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

        {/* Card */}
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

        {/* Checkbox */}
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

        {/* Collapsible */}
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

        {/* Context Menu */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Context Menu
          </h2>
          <ContextMenu>
            <ContextMenuTrigger className="flex h-[100px] w-[200px] items-center justify-center rounded-md border border-dashed text-sm">
              Right click here
            </ContextMenuTrigger>
            <ContextMenuContent>
              <ContextMenuItem>Back</ContextMenuItem>
              <ContextMenuItem>Forward</ContextMenuItem>
              <ContextMenuItem>Reload</ContextMenuItem>
              <ContextMenuSeparator />
              <ContextMenuItem>View Page Source</ContextMenuItem>
              <ContextMenuItem>Inspect</ContextMenuItem>
            </ContextMenuContent>
          </ContextMenu>
        </section>

        {/* Dialog */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Dialog
          </h2>
          <Dialog>
            <DialogTrigger render={<Button variant="outline" />}>
              Open Dialog
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Edit Profile</DialogTitle>
                <DialogDescription>
                  Make changes to your profile here.
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Name</Label>
                  <Input id="name" defaultValue="John Doe" />
                </div>
              </div>
              <DialogFooter>
                <Button>Save changes</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </section>

        {/* Drawer */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Drawer
          </h2>
          <Drawer>
            <DrawerTrigger asChild>
              <Button variant="outline">Open Drawer</Button>
            </DrawerTrigger>
            <DrawerContent>
              <DrawerHeader>
                <DrawerTitle>Edit profile</DrawerTitle>
                <DrawerDescription>
                  Make changes to your profile here.
                </DrawerDescription>
              </DrawerHeader>
              <DrawerFooter>
                <Button>Submit</Button>
                <DrawerClose asChild>
                  <Button variant="outline">Cancel</Button>
                </DrawerClose>
              </DrawerFooter>
            </DrawerContent>
          </Drawer>
        </section>

        {/* Dropdown Menu */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Dropdown Menu
          </h2>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="outline" />}>
              Open Menu
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>My Account</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>Profile</DropdownMenuItem>
              <DropdownMenuItem>Settings</DropdownMenuItem>
              <DropdownMenuItem>Billing</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">Log out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </section>

        {/* Hover Card */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Hover Card
          </h2>
          <HoverCard>
            <HoverCardTrigger render={<Button variant="link" />}>
              @nextjs
            </HoverCardTrigger>
            <HoverCardContent className="w-80">
              <div className="flex justify-between space-x-4">
                <Avatar>
                  <AvatarImage src="https://github.com/vercel.png" />
                  <AvatarFallback>VC</AvatarFallback>
                </Avatar>
                <div className="space-y-1">
                  <h4 className="text-sm font-medium">@nextjs</h4>
                  <p className="text-sm text-muted-foreground">
                    The React Framework – created and maintained by @vercel.
                  </p>
                </div>
              </div>
            </HoverCardContent>
          </HoverCard>
        </section>

        {/* Input */}
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

        {/* Input OTP */}
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

        {/* Kbd */}
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

        {/* Label */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Label
          </h2>
          <div className="flex flex-col gap-2 max-w-sm">
            <Label htmlFor="email-label">Email</Label>
            <Input id="email-label" type="email" placeholder="Enter email" />
          </div>
        </section>

        {/* Pagination */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Pagination
          </h2>
          <Pagination>
            <PaginationContent>
              <PaginationItem>
                <PaginationPrevious href="#" />
              </PaginationItem>
              <PaginationItem>
                <PaginationLink href="#">1</PaginationLink>
              </PaginationItem>
              <PaginationItem>
                <PaginationLink href="#" isActive>
                  2
                </PaginationLink>
              </PaginationItem>
              <PaginationItem>
                <PaginationLink href="#">3</PaginationLink>
              </PaginationItem>
              <PaginationItem>
                <PaginationEllipsis />
              </PaginationItem>
              <PaginationItem>
                <PaginationNext href="#" />
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </section>

        {/* Popover */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Popover
          </h2>
          <Popover>
            <PopoverTrigger render={<Button variant="outline" />}>
              Open Popover
            </PopoverTrigger>
            <PopoverContent>
              <div className="grid gap-4">
                <div className="space-y-2">
                  <h4 className="font-medium leading-none">Dimensions</h4>
                  <p className="text-sm text-muted-foreground">
                    Set the dimensions for the layer.
                  </p>
                </div>
              </div>
            </PopoverContent>
          </Popover>
        </section>

        {/* Progress */}
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

        {/* Radio Group */}
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

        {/* Resizable */}
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

        {/* Scroll Area */}
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

        {/* Select */}
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

        {/* Separator */}
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

        {/* Sheet */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Sheet
          </h2>
          <Sheet>
            <SheetTrigger render={<Button variant="outline" />}>
              Open Sheet
            </SheetTrigger>
            <SheetContent>
              <SheetHeader>
                <SheetTitle>Edit profile</SheetTitle>
                <SheetDescription>
                  Make changes to your profile here.
                </SheetDescription>
              </SheetHeader>
            </SheetContent>
          </Sheet>
        </section>

        {/* Skeleton */}
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

        {/* Slider */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Slider
          </h2>
          <div className="max-w-md">
            <Slider defaultValue={[50]} max={100} step={1} />
          </div>
        </section>

        {/* Spinner */}
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

        {/* Switch */}
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

        {/* Table */}
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

        {/* Tabs */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Tabs
          </h2>
          <Tabs defaultValue="account" className="w-full max-w-md">
            <TabsList>
              <TabsTrigger value="account">Account</TabsTrigger>
              <TabsTrigger value="password">Password</TabsTrigger>
              <TabsTrigger value="settings">Settings</TabsTrigger>
            </TabsList>
            <TabsContent value="account">
              Make changes to your account here.
            </TabsContent>
            <TabsContent value="password">
              Change your password here.
            </TabsContent>
            <TabsContent value="settings">
              Manage your settings here.
            </TabsContent>
          </Tabs>
        </section>

        {/* Textarea */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Textarea
          </h2>
          <div className="max-w-md">
            <Textarea placeholder="Type your message here..." />
          </div>
        </section>

        {/* Toggle */}
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

        {/* Toggle Group */}
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

        {/* Tooltip */}
        <section className="space-y-4">
          <h2 className="text-xs font-mono uppercase tracking-widest text-muted-foreground">
            Tooltip
          </h2>
          <div className="flex gap-4">
            <Tooltip>
              <TooltipTrigger render={<Button variant="outline" />}>
                Hover me
              </TooltipTrigger>
              <TooltipContent>
                <p>This is a tooltip</p>
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger render={<Button variant="outline" size="icon" />}>
                <Search />
              </TooltipTrigger>
              <TooltipContent>
                <p>
                  Search <Kbd>⌘K</Kbd>
                </p>
              </TooltipContent>
            </Tooltip>
          </div>
        </section>
      </div>
    </div>
  )
}
