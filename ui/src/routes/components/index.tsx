import {
  ButtonSection,
  ButtonGroupSection,
  ToggleSection,
  ToggleGroupSection,
} from '@/features/components-page/sections/buttons'
import {
  AvatarSection,
  BadgeSection,
  CalendarSection,
  CarouselSection,
  EmptySection,
  TableSection,
} from '@/features/components-page/sections/data-display'
import {
  AlertSection,
  ProgressSection,
  SkeletonSection,
  SpinnerSection,
} from '@/features/components-page/sections/feedback'
import {
  InputSection,
  InputGroupSection,
  InputOTPSection,
  TextareaSection,
  SelectSection,
  ComboboxSection,
  CheckboxSection,
  RadioGroupSection,
  SwitchSection,
  SliderSection,
  FieldSection,
  LabelSection,
  KbdSection,
} from '@/features/components-page/sections/form-inputs'
import {
  AccordionSection,
  AspectRatioSection,
  CardSection,
  CollapsibleSection,
  ItemSection,
  ResizableSection,
  ScrollAreaSection,
  SeparatorSection,
} from '@/features/components-page/sections/layout'
import {
  BreadcrumbSection,
  CommandSection,
  MenubarSection,
  NavigationMenuSection,
  PaginationSection,
  TabsSection,
} from '@/features/components-page/sections/navigation'
import {
  AlertDialogSection,
  ContextMenuSection,
  DialogSection,
  DrawerSection,
  DropdownMenuSection,
  HoverCardSection,
  PopoverSection,
  SheetSection,
  TooltipSection,
} from '@/features/components-page/sections/overlays'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/components/')({
  component: ComponentsPage,
})

function ComponentsPage() {
  return (
    <div className="min-h-screen bg-background/80 backdrop-blur-sm p-12">
      <div className="mx-auto max-w-4xl space-y-12">
        {/* Buttons */}
        <ButtonSection />
        <ButtonGroupSection />
        <ToggleSection />
        <ToggleGroupSection />

        {/* Layout */}
        <AccordionSection />
        <AspectRatioSection />
        <CardSection />
        <CollapsibleSection />
        <ItemSection />
        <ResizableSection />
        <ScrollAreaSection />
        <SeparatorSection />

        {/* Form Inputs */}
        <InputSection />
        <InputGroupSection />
        <InputOTPSection />
        <TextareaSection />
        <SelectSection />
        <ComboboxSection />
        <CheckboxSection />
        <RadioGroupSection />
        <SwitchSection />
        <SliderSection />
        <FieldSection />
        <LabelSection />
        <KbdSection />

        {/* Navigation */}
        <BreadcrumbSection />
        <CommandSection />
        <MenubarSection />
        <NavigationMenuSection />
        <PaginationSection />
        <TabsSection />

        {/* Data Display */}
        <AvatarSection />
        <BadgeSection />
        <CalendarSection />
        <CarouselSection />
        <EmptySection />
        <TableSection />

        {/* Overlays */}
        <AlertDialogSection />
        <ContextMenuSection />
        <DialogSection />
        <DrawerSection />
        <DropdownMenuSection />
        <HoverCardSection />
        <PopoverSection />
        <SheetSection />
        <TooltipSection />

        {/* Feedback */}
        <AlertSection />
        <ProgressSection />
        <SkeletonSection />
        <SpinnerSection />
      </div>
    </div>
  )
}
