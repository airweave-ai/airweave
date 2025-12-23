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
import { Button } from '@/components/ui/button'
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
import { Kbd } from '@/components/ui/kbd'
import { Label } from '@/components/ui/label'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Search } from 'lucide-react'

export function AlertDialogSection() {
  return (
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
  )
}

export function ContextMenuSection() {
  return (
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
  )
}

export function DialogSection() {
  return (
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
  )
}

export function DrawerSection() {
  return (
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
  )
}

export function DropdownMenuSection() {
  return (
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
  )
}

export function HoverCardSection() {
  return (
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
  )
}

export function PopoverSection() {
  return (
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
  )
}

export function SheetSection() {
  return (
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
  )
}

export function TooltipSection() {
  return (
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
  )
}
