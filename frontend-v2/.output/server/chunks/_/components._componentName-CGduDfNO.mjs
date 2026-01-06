import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { B as Badge } from "./badge-B1TPqLQ8.mjs";
import { c as createLucideIcon, R as Route$6, B as Button, T as Tooltip, p as TooltipTrigger, r as TooltipContent, P as Plus, S as Sheet, s as SheetTrigger, t as SheetContent, v as SheetHeader, w as SheetTitle, x as SheetDescription, y as SheetFooter, z as SheetClose, A as Search, E as DropdownMenu, F as DropdownMenuTrigger, G as DropdownMenuContent, H as DropdownMenuLabel, I as DropdownMenuSeparator, J as DropdownMenuGroup, K as DropdownMenuItem, M as DropdownMenuShortcut, N as DropdownMenuSub, O as DropdownMenuSubTrigger, Q as DropdownMenuSubContent, V as LogOut, D as Dialog, W as DialogTrigger, k as DialogContent, l as DialogHeader, m as DialogTitle, n as DialogDescription, Y as DialogFooter, Z as DialogClose, _ as Command, $ as CommandInput, a0 as CommandList, a1 as CommandEmpty, a2 as CommandGroup, a3 as CommandItem, a4 as CommandSeparator, a5 as CommandShortcut, a6 as Avatar, a7 as AvatarImage, a8 as AvatarFallback, h as Check, a as cn } from "./router-BGxBdlkD.mjs";
import { C as Card, c as CardContent, a as CardHeader, b as CardTitle, d as CardDescription, e as CardFooter, f as CardAction } from "./card-DGG0csos.mjs";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { u as uiComponents, P as Package } from "./components.gen-2SPXrlVv.mjs";
import { E as ErrorState, A as AlertDialog, a as AlertDialogTrigger, b as AlertDialogContent, c as AlertDialogHeader, d as AlertDialogTitle, e as AlertDialogDescription, f as AlertDialogFooter, g as AlertDialogCancel, h as AlertDialogAction, C as Copy } from "./error-state-BYmPP-hR.mjs";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { T as Table, a as TableCaption, b as TableHeader, c as TableRow, d as TableHead, e as TableBody, f as TableCell, g as TableFooter, C as Checkbox } from "./checkbox-L51m4-da.mjs";
import { E as EmptyState } from "./empty-state-BldPO3ai.mjs";
import { L as LoadingState } from "./loading-state-CJE8ekwd.mjs";
import * as SeparatorPrimitive from "@radix-ui/react-separator";
import { T as Tabs, a as TabsList, b as TabsTrigger, c as TabsContent } from "./tabs-ChSqzczQ.mjs";
import { A as ArrowLeft, F as FileText, S as Settings, M as MessageSquare } from "./settings.mjs";
import { U as Users, C as Cloud } from "./users.mjs";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "@tanstack/react-query";
import "@tanstack/react-query-persist-client";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "zustand";
import "zustand/middleware";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "sonner";
import "idb-keyval";
import "@radix-ui/react-alert-dialog";
import "@radix-ui/react-checkbox";
import "@radix-ui/react-tabs";
const __iconNode$c = [
  ["rect", { width: "16", height: "20", x: "4", y: "2", rx: "2", key: "1nb95v" }],
  ["line", { x1: "8", x2: "16", y1: "6", y2: "6", key: "x4nwl0" }],
  ["line", { x1: "16", x2: "16", y1: "14", y2: "18", key: "wjye3r" }],
  ["path", { d: "M16 10h.01", key: "1m94wz" }],
  ["path", { d: "M12 10h.01", key: "1nrarc" }],
  ["path", { d: "M8 10h.01", key: "19clt8" }],
  ["path", { d: "M12 14h.01", key: "1etili" }],
  ["path", { d: "M8 14h.01", key: "6423bh" }],
  ["path", { d: "M12 18h.01", key: "mhygvu" }],
  ["path", { d: "M8 18h.01", key: "lrp35t" }]
];
const Calculator = createLucideIcon("calculator", __iconNode$c);
const __iconNode$b = [
  ["path", { d: "M8 2v4", key: "1cmpym" }],
  ["path", { d: "M16 2v4", key: "4m81vk" }],
  ["rect", { width: "18", height: "18", x: "3", y: "4", rx: "2", key: "1hopcy" }],
  ["path", { d: "M3 10h18", key: "8toen8" }]
];
const Calendar = createLucideIcon("calendar", __iconNode$b);
const __iconNode$a = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M8 12h8", key: "1wcyev" }],
  ["path", { d: "M12 8v8", key: "napkw2" }]
];
const CirclePlus = createLucideIcon("circle-plus", __iconNode$a);
const __iconNode$9 = [
  ["path", { d: "m16 18 6-6-6-6", key: "eg8j8" }],
  ["path", { d: "m8 6-6 6 6 6", key: "ppft3o" }]
];
const Code = createLucideIcon("code", __iconNode$9);
const __iconNode$8 = [
  ["rect", { width: "20", height: "14", x: "2", y: "5", rx: "2", key: "ynyp8z" }],
  ["line", { x1: "2", x2: "22", y1: "10", y2: "10", key: "1b3vmo" }]
];
const CreditCard = createLucideIcon("credit-card", __iconNode$8);
const __iconNode$7 = [
  [
    "path",
    {
      d: "M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4",
      key: "tonef"
    }
  ],
  ["path", { d: "M9 18c-4.51 2-5-2-7-2", key: "9comsn" }]
];
const Github = createLucideIcon("github", __iconNode$7);
const __iconNode$6 = [
  ["polyline", { points: "22 12 16 12 14 15 10 15 8 12 2 12", key: "o97t9d" }],
  [
    "path",
    {
      d: "M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z",
      key: "oot6mr"
    }
  ]
];
const Inbox = createLucideIcon("inbox", __iconNode$6);
const __iconNode$5 = [
  ["path", { d: "M10 8h.01", key: "1r9ogq" }],
  ["path", { d: "M12 12h.01", key: "1mp3jc" }],
  ["path", { d: "M14 8h.01", key: "1primd" }],
  ["path", { d: "M16 12h.01", key: "1l6xoz" }],
  ["path", { d: "M18 8h.01", key: "emo2bl" }],
  ["path", { d: "M6 8h.01", key: "x9i8wu" }],
  ["path", { d: "M7 16h10", key: "wp8him" }],
  ["path", { d: "M8 12h.01", key: "czm47f" }],
  ["rect", { width: "20", height: "16", x: "2", y: "4", rx: "2", key: "18n3k1" }]
];
const Keyboard = createLucideIcon("keyboard", __iconNode$5);
const __iconNode$4 = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "m4.93 4.93 4.24 4.24", key: "1ymg45" }],
  ["path", { d: "m14.83 9.17 4.24-4.24", key: "1cb5xl" }],
  ["path", { d: "m14.83 14.83 4.24 4.24", key: "q42g0n" }],
  ["path", { d: "m9.17 14.83-4.24 4.24", key: "bqpfvv" }],
  ["circle", { cx: "12", cy: "12", r: "4", key: "4exip2" }]
];
const LifeBuoy = createLucideIcon("life-buoy", __iconNode$4);
const __iconNode$3 = [
  ["path", { d: "m22 7-8.991 5.727a2 2 0 0 1-2.009 0L2 7", key: "132q7q" }],
  ["rect", { x: "2", y: "4", width: "20", height: "16", rx: "2", key: "izxlao" }]
];
const Mail = createLucideIcon("mail", __iconNode$3);
const __iconNode$2 = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M8 14s1.5 2 4 2 4-2 4-2", key: "1y1vjs" }],
  ["line", { x1: "9", x2: "9.01", y1: "9", y2: "9", key: "yxxnd0" }],
  ["line", { x1: "15", x2: "15.01", y1: "9", y2: "9", key: "1p4y9e" }]
];
const Smile = createLucideIcon("smile", __iconNode$2);
const __iconNode$1 = [
  ["path", { d: "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2", key: "1yyitq" }],
  ["circle", { cx: "9", cy: "7", r: "4", key: "nufk8" }],
  ["line", { x1: "19", x2: "19", y1: "8", y2: "14", key: "1bvyxn" }],
  ["line", { x1: "22", x2: "16", y1: "11", y2: "11", key: "1shjgl" }]
];
const UserPlus = createLucideIcon("user-plus", __iconNode$1);
const __iconNode = [
  ["path", { d: "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2", key: "975kel" }],
  ["circle", { cx: "12", cy: "7", r: "4", key: "17ys0d" }]
];
const User = createLucideIcon("user", __iconNode);
function Separator({
  className,
  orientation = "horizontal",
  decorative = true,
  ...props
}) {
  return /* @__PURE__ */ jsx(
    SeparatorPrimitive.Root,
    {
      "data-slot": "separator",
      decorative,
      orientation,
      className: cn(
        "bg-border shrink-0 data-[orientation=horizontal]:h-px data-[orientation=horizontal]:w-full data-[orientation=vertical]:h-full data-[orientation=vertical]:w-px",
        className
      ),
      ...props
    }
  );
}
function Skeleton({ className, ...props }) {
  return /* @__PURE__ */ jsx(
    "div",
    {
      "data-slot": "skeleton",
      className: cn("bg-accent animate-pulse rounded-md", className),
      ...props
    }
  );
}
const alertDialogPreview = {
  variants: [
    {
      title: "Default",
      description: "A modal dialog that interrupts the user with important content and expects a response",
      preview: /* @__PURE__ */ jsxs(AlertDialog, { children: [
        /* @__PURE__ */ jsx(AlertDialogTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Show Dialog" }) }),
        /* @__PURE__ */ jsxs(AlertDialogContent, { children: [
          /* @__PURE__ */ jsxs(AlertDialogHeader, { children: [
            /* @__PURE__ */ jsx(AlertDialogTitle, { children: "Are you absolutely sure?" }),
            /* @__PURE__ */ jsx(AlertDialogDescription, { children: "This action cannot be undone. This will permanently delete your account and remove your data from our servers." })
          ] }),
          /* @__PURE__ */ jsxs(AlertDialogFooter, { children: [
            /* @__PURE__ */ jsx(AlertDialogCancel, { children: "Cancel" }),
            /* @__PURE__ */ jsx(AlertDialogAction, { children: "Continue" })
          ] })
        ] })
      ] }),
      code: `<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="outline">Show Dialog</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
      <AlertDialogDescription>
        This action cannot be undone. This will permanently delete your
        account and remove your data from our servers.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction>Continue</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>`
    },
    {
      title: "Destructive Action",
      description: "Alert dialog with a destructive action button",
      preview: /* @__PURE__ */ jsxs(AlertDialog, { children: [
        /* @__PURE__ */ jsx(AlertDialogTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "destructive", children: "Delete Account" }) }),
        /* @__PURE__ */ jsxs(AlertDialogContent, { children: [
          /* @__PURE__ */ jsxs(AlertDialogHeader, { children: [
            /* @__PURE__ */ jsx(AlertDialogTitle, { children: "Delete Account" }),
            /* @__PURE__ */ jsx(AlertDialogDescription, { children: "Are you sure you want to delete your account? All of your data will be permanently removed. This action cannot be undone." })
          ] }),
          /* @__PURE__ */ jsxs(AlertDialogFooter, { children: [
            /* @__PURE__ */ jsx(AlertDialogCancel, { children: "Cancel" }),
            /* @__PURE__ */ jsx(AlertDialogAction, { className: "bg-destructive hover:bg-destructive/90 text-white", children: "Delete" })
          ] })
        ] })
      ] }),
      code: `<AlertDialog>
  <AlertDialogTrigger asChild>
    <Button variant="destructive">Delete Account</Button>
  </AlertDialogTrigger>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Delete Account</AlertDialogTitle>
      <AlertDialogDescription>
        Are you sure you want to delete your account? All of your data
        will be permanently removed. This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction className="bg-destructive text-white hover:bg-destructive/90">
        Delete
      </AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>`
    }
  ]
};
const avatarPreview = {
  variants: [
    {
      title: "Default",
      description: "Avatar with an image and fallback initials",
      preview: /* @__PURE__ */ jsxs(Avatar, { children: [
        /* @__PURE__ */ jsx(AvatarImage, { src: "https://github.com/shadcn.png", alt: "@shadcn" }),
        /* @__PURE__ */ jsx(AvatarFallback, { children: "CN" })
      ] }),
      code: `<Avatar>
  <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
  <AvatarFallback>CN</AvatarFallback>
</Avatar>`
    },
    {
      title: "Fallback States",
      description: "Avatar displays fallback content when image fails to load",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-4", children: [
        /* @__PURE__ */ jsxs(Avatar, { children: [
          /* @__PURE__ */ jsx(AvatarImage, { src: "https://github.com/shadcn.png", alt: "@shadcn" }),
          /* @__PURE__ */ jsx(AvatarFallback, { children: "CN" })
        ] }),
        /* @__PURE__ */ jsx(Avatar, { children: /* @__PURE__ */ jsx(AvatarFallback, { children: "JD" }) }),
        /* @__PURE__ */ jsx(Avatar, { children: /* @__PURE__ */ jsx(AvatarFallback, { children: "AB" }) })
      ] }),
      code: `{/* With image */}
<Avatar>
  <AvatarImage src="https://github.com/shadcn.png" alt="@shadcn" />
  <AvatarFallback>CN</AvatarFallback>
</Avatar>

{/* Fallback only */}
<Avatar>
  <AvatarFallback>JD</AvatarFallback>
</Avatar>`
    },
    {
      title: "Sizes",
      description: "Avatars can be sized using className",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-4", children: [
        /* @__PURE__ */ jsx(Avatar, { className: "size-6", children: /* @__PURE__ */ jsx(AvatarFallback, { className: "text-xs", children: "SM" }) }),
        /* @__PURE__ */ jsx(Avatar, { children: /* @__PURE__ */ jsx(AvatarFallback, { children: "MD" }) }),
        /* @__PURE__ */ jsx(Avatar, { className: "size-12", children: /* @__PURE__ */ jsx(AvatarFallback, { children: "LG" }) }),
        /* @__PURE__ */ jsx(Avatar, { className: "size-16", children: /* @__PURE__ */ jsx(AvatarFallback, { className: "text-lg", children: "XL" }) })
      ] }),
      code: `<Avatar className="size-6">
  <AvatarFallback className="text-xs">SM</AvatarFallback>
</Avatar>
<Avatar>
  <AvatarFallback>MD</AvatarFallback>
</Avatar>
<Avatar className="size-12">
  <AvatarFallback>LG</AvatarFallback>
</Avatar>
<Avatar className="size-16">
  <AvatarFallback className="text-lg">XL</AvatarFallback>
</Avatar>`
    }
  ]
};
const badgePreview = {
  variants: [
    {
      title: "Default Variants",
      description: "Badges come in different visual styles for various contexts",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [
        /* @__PURE__ */ jsx(Badge, { variant: "default", children: "Default" }),
        /* @__PURE__ */ jsx(Badge, { variant: "secondary", children: "Secondary" }),
        /* @__PURE__ */ jsx(Badge, { variant: "destructive", children: "Destructive" }),
        /* @__PURE__ */ jsx(Badge, { variant: "outline", children: "Outline" })
      ] }),
      code: `<Badge variant="default">Default</Badge>
<Badge variant="secondary">Secondary</Badge>
<Badge variant="destructive">Destructive</Badge>
<Badge variant="outline">Outline</Badge>`
    },
    {
      title: "With Icons",
      description: "Badges can include icons alongside text",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap items-center gap-2", children: [
        /* @__PURE__ */ jsxs(Badge, { children: [
          /* @__PURE__ */ jsx(
            "svg",
            {
              className: "size-3",
              fill: "none",
              stroke: "currentColor",
              viewBox: "0 0 24 24",
              children: /* @__PURE__ */ jsx(
                "path",
                {
                  strokeLinecap: "round",
                  strokeLinejoin: "round",
                  strokeWidth: 2,
                  d: "M5 13l4 4L19 7"
                }
              )
            }
          ),
          "Verified"
        ] }),
        /* @__PURE__ */ jsxs(Badge, { variant: "secondary", children: [
          /* @__PURE__ */ jsx(
            "svg",
            {
              className: "size-3",
              fill: "none",
              stroke: "currentColor",
              viewBox: "0 0 24 24",
              children: /* @__PURE__ */ jsx(
                "path",
                {
                  strokeLinecap: "round",
                  strokeLinejoin: "round",
                  strokeWidth: 2,
                  d: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                }
              )
            }
          ),
          "Pending"
        ] }),
        /* @__PURE__ */ jsxs(Badge, { variant: "destructive", children: [
          /* @__PURE__ */ jsx(
            "svg",
            {
              className: "size-3",
              fill: "none",
              stroke: "currentColor",
              viewBox: "0 0 24 24",
              children: /* @__PURE__ */ jsx(
                "path",
                {
                  strokeLinecap: "round",
                  strokeLinejoin: "round",
                  strokeWidth: 2,
                  d: "M6 18L18 6M6 6l12 12"
                }
              )
            }
          ),
          "Error"
        ] })
      ] }),
      code: `<Badge>
  <CheckIcon className="size-3" />
  Verified
</Badge>
<Badge variant="secondary">
  <ClockIcon className="size-3" />
  Pending
</Badge>
<Badge variant="destructive">
  <XIcon className="size-3" />
  Error
</Badge>`
    },
    {
      title: "As Link",
      description: "Badges can be rendered as links using asChild",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ jsx(Badge, { asChild: true, children: /* @__PURE__ */ jsx("a", { href: "#", children: "Clickable" }) }),
        /* @__PURE__ */ jsx(Badge, { variant: "outline", asChild: true, children: /* @__PURE__ */ jsx("a", { href: "#", children: "Link Badge" }) })
      ] }),
      code: `<Badge asChild>
  <a href="#">Clickable</a>
</Badge>
<Badge variant="outline" asChild>
  <a href="#">Link Badge</a>
</Badge>`
    }
  ]
};
const buttonPreview = {
  variants: [
    {
      title: "Default Variants",
      description: "The button component supports multiple visual variants",
      preview: /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx(Button, { variant: "default", children: "Default" }),
        /* @__PURE__ */ jsx(Button, { variant: "secondary", children: "Secondary" }),
        /* @__PURE__ */ jsx(Button, { variant: "destructive", children: "Destructive" }),
        /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Outline" }),
        /* @__PURE__ */ jsx(Button, { variant: "ghost", children: "Ghost" }),
        /* @__PURE__ */ jsx(Button, { variant: "link", children: "Link" })
      ] }),
      code: `<Button variant="default">Default</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="destructive">Destructive</Button>
<Button variant="outline">Outline</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="link">Link</Button>`
    },
    {
      title: "Sizes",
      description: "Buttons come in different sizes for various use cases",
      preview: /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx(Button, { size: "sm", children: "Small" }),
        /* @__PURE__ */ jsx(Button, { size: "default", children: "Default" }),
        /* @__PURE__ */ jsx(Button, { size: "lg", children: "Large" }),
        /* @__PURE__ */ jsx(Button, { size: "icon", children: /* @__PURE__ */ jsx(Package, { className: "h-4 w-4" }) })
      ] }),
      code: `<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
<Button size="icon"><Icon /></Button>`
    },
    {
      title: "States",
      description: "Buttons can be disabled or used as child components",
      preview: /* @__PURE__ */ jsxs(Fragment, { children: [
        /* @__PURE__ */ jsx(Button, { disabled: true, children: "Disabled" }),
        /* @__PURE__ */ jsx(Button, { asChild: true, children: /* @__PURE__ */ jsx("a", { href: "#", children: "As Link" }) })
      ] }),
      code: `<Button disabled>Disabled</Button>
<Button asChild>
  <a href="#">As Link</a>
</Button>`
    }
  ]
};
const cardPreview = {
  variants: [
    {
      title: "Default",
      description: "A basic card with header, content, and footer",
      preview: /* @__PURE__ */ jsxs(Card, { className: "w-[350px]", children: [
        /* @__PURE__ */ jsxs(CardHeader, { children: [
          /* @__PURE__ */ jsx(CardTitle, { children: "Card Title" }),
          /* @__PURE__ */ jsx(CardDescription, { children: "Card description goes here to provide context." })
        ] }),
        /* @__PURE__ */ jsx(CardContent, { children: /* @__PURE__ */ jsx("p", { className: "text-sm", children: "This is the main content area of the card. You can put any content here including forms, text, images, and more." }) }),
        /* @__PURE__ */ jsx(CardFooter, { children: /* @__PURE__ */ jsx(Button, { className: "w-full", children: "Action" }) })
      ] }),
      code: `<Card className="w-[350px]">
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>
      Card description goes here to provide context.
    </CardDescription>
  </CardHeader>
  <CardContent>
    <p>This is the main content area of the card.</p>
  </CardContent>
  <CardFooter>
    <Button className="w-full">Action</Button>
  </CardFooter>
</Card>`
    },
    {
      title: "With Action",
      description: "Card header can include an action button",
      preview: /* @__PURE__ */ jsxs(Card, { className: "w-[350px]", children: [
        /* @__PURE__ */ jsxs(CardHeader, { children: [
          /* @__PURE__ */ jsx(CardTitle, { children: "Notifications" }),
          /* @__PURE__ */ jsx(CardDescription, { children: "You have 3 unread messages." }),
          /* @__PURE__ */ jsx(CardAction, { children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Mark all read" }) })
        ] }),
        /* @__PURE__ */ jsx(CardContent, { children: /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
          /* @__PURE__ */ jsx("div", { className: "bg-muted rounded-md p-3 text-sm", children: "New message from John" }),
          /* @__PURE__ */ jsx("div", { className: "bg-muted rounded-md p-3 text-sm", children: "Meeting reminder for tomorrow" }),
          /* @__PURE__ */ jsx("div", { className: "bg-muted rounded-md p-3 text-sm", children: "Your report is ready" })
        ] }) })
      ] }),
      code: `<Card>
  <CardHeader>
    <CardTitle>Notifications</CardTitle>
    <CardDescription>You have 3 unread messages.</CardDescription>
    <CardAction>
      <Button variant="outline" size="sm">Mark all read</Button>
    </CardAction>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>`
    },
    {
      title: "Form Card",
      description: "Card containing a simple form",
      preview: /* @__PURE__ */ jsxs(Card, { className: "w-[350px]", children: [
        /* @__PURE__ */ jsxs(CardHeader, { children: [
          /* @__PURE__ */ jsx(CardTitle, { children: "Create project" }),
          /* @__PURE__ */ jsx(CardDescription, { children: "Deploy your new project in one-click." })
        ] }),
        /* @__PURE__ */ jsx(CardContent, { children: /* @__PURE__ */ jsx("form", { children: /* @__PURE__ */ jsx("div", { className: "grid w-full items-center gap-4", children: /* @__PURE__ */ jsxs("div", { className: "flex flex-col space-y-1.5", children: [
          /* @__PURE__ */ jsx("label", { htmlFor: "name", className: "text-sm font-medium", children: "Name" }),
          /* @__PURE__ */ jsx(Input, { id: "name", placeholder: "Name of your project" })
        ] }) }) }) }),
        /* @__PURE__ */ jsxs(CardFooter, { className: "flex justify-between", children: [
          /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Cancel" }),
          /* @__PURE__ */ jsx(Button, { children: "Deploy" })
        ] })
      ] }),
      code: `<Card className="w-[350px]">
  <CardHeader>
    <CardTitle>Create project</CardTitle>
    <CardDescription>Deploy your new project in one-click.</CardDescription>
  </CardHeader>
  <CardContent>
    <form>
      <div className="grid w-full items-center gap-4">
        <div className="flex flex-col space-y-1.5">
          <label htmlFor="name">Name</label>
          <Input id="name" placeholder="Name of your project" />
        </div>
      </div>
    </form>
  </CardContent>
  <CardFooter className="flex justify-between">
    <Button variant="outline">Cancel</Button>
    <Button>Deploy</Button>
  </CardFooter>
</Card>`
    }
  ]
};
const checkboxPreview = {
  variants: [
    {
      title: "Default",
      description: "A basic checkbox that can be checked or unchecked",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
        /* @__PURE__ */ jsx(Checkbox, { id: "terms" }),
        /* @__PURE__ */ jsx(
          "label",
          {
            htmlFor: "terms",
            className: "text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
            children: "Accept terms and conditions"
          }
        )
      ] }),
      code: `<div className="flex items-center space-x-2">
  <Checkbox id="terms" />
  <label htmlFor="terms" className="text-sm font-medium">
    Accept terms and conditions
  </label>
</div>`
    },
    {
      title: "States",
      description: "Checkbox in different states: unchecked, checked, and disabled",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
          /* @__PURE__ */ jsx(Checkbox, { id: "unchecked" }),
          /* @__PURE__ */ jsx("label", { htmlFor: "unchecked", className: "text-sm", children: "Unchecked" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
          /* @__PURE__ */ jsx(Checkbox, { id: "checked", defaultChecked: true }),
          /* @__PURE__ */ jsx("label", { htmlFor: "checked", className: "text-sm", children: "Checked" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
          /* @__PURE__ */ jsx(Checkbox, { id: "disabled", disabled: true }),
          /* @__PURE__ */ jsx("label", { htmlFor: "disabled", className: "text-sm opacity-50", children: "Disabled" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
          /* @__PURE__ */ jsx(Checkbox, { id: "disabled-checked", disabled: true, defaultChecked: true }),
          /* @__PURE__ */ jsx("label", { htmlFor: "disabled-checked", className: "text-sm opacity-50", children: "Disabled Checked" })
        ] })
      ] }),
      code: `<Checkbox id="unchecked" />
<Checkbox id="checked" defaultChecked />
<Checkbox id="disabled" disabled />
<Checkbox id="disabled-checked" disabled defaultChecked />`
    },
    {
      title: "Indeterminate",
      description: "Checkbox with indeterminate state for partial selections",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-2", children: [
        /* @__PURE__ */ jsx(Checkbox, { id: "indeterminate", indeterminate: true }),
        /* @__PURE__ */ jsx("label", { htmlFor: "indeterminate", className: "text-sm", children: "Select all (partial)" })
      ] }),
      code: `<Checkbox id="indeterminate" indeterminate />`
    }
  ]
};
const commandPreview = {
  variants: [
    {
      title: "Default",
      description: "A command menu with search and grouped items",
      preview: /* @__PURE__ */ jsxs(Command, { className: "rounded-lg border shadow-md md:min-w-[450px]", children: [
        /* @__PURE__ */ jsx(CommandInput, { placeholder: "Type a command or search..." }),
        /* @__PURE__ */ jsxs(CommandList, { children: [
          /* @__PURE__ */ jsx(CommandEmpty, { children: "No results found." }),
          /* @__PURE__ */ jsxs(CommandGroup, { heading: "Suggestions", children: [
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(Calendar, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Calendar" })
            ] }),
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(Smile, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Search Emoji" })
            ] }),
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(Calculator, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Calculator" })
            ] })
          ] }),
          /* @__PURE__ */ jsx(CommandSeparator, {}),
          /* @__PURE__ */ jsxs(CommandGroup, { heading: "Settings", children: [
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(User, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Profile" }),
              /* @__PURE__ */ jsx(CommandShortcut, { children: "⌘P" })
            ] }),
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(CreditCard, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Billing" }),
              /* @__PURE__ */ jsx(CommandShortcut, { children: "⌘B" })
            ] }),
            /* @__PURE__ */ jsxs(CommandItem, { children: [
              /* @__PURE__ */ jsx(Settings, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Settings" }),
              /* @__PURE__ */ jsx(CommandShortcut, { children: "⌘S" })
            ] })
          ] })
        ] })
      ] }),
      code: `<Command className="rounded-lg border shadow-md">
  <CommandInput placeholder="Type a command or search..." />
  <CommandList>
    <CommandEmpty>No results found.</CommandEmpty>
    <CommandGroup heading="Suggestions">
      <CommandItem>
        <Calendar className="mr-2 h-4 w-4" />
        <span>Calendar</span>
      </CommandItem>
      <CommandItem>
        <Smile className="mr-2 h-4 w-4" />
        <span>Search Emoji</span>
      </CommandItem>
    </CommandGroup>
    <CommandSeparator />
    <CommandGroup heading="Settings">
      <CommandItem>
        <User className="mr-2 h-4 w-4" />
        <span>Profile</span>
        <CommandShortcut>⌘P</CommandShortcut>
      </CommandItem>
    </CommandGroup>
  </CommandList>
</Command>`
    },
    {
      title: "Simple List",
      description: "A simpler command list without search",
      preview: /* @__PURE__ */ jsx(Command, { className: "rounded-lg border shadow-md md:min-w-[300px]", children: /* @__PURE__ */ jsx(CommandList, { children: /* @__PURE__ */ jsxs(CommandGroup, { children: [
        /* @__PURE__ */ jsxs(CommandItem, { children: [
          /* @__PURE__ */ jsx(User, { className: "mr-2 h-4 w-4" }),
          /* @__PURE__ */ jsx("span", { children: "Profile" })
        ] }),
        /* @__PURE__ */ jsxs(CommandItem, { children: [
          /* @__PURE__ */ jsx(Settings, { className: "mr-2 h-4 w-4" }),
          /* @__PURE__ */ jsx("span", { children: "Settings" })
        ] }),
        /* @__PURE__ */ jsxs(CommandItem, { children: [
          /* @__PURE__ */ jsx(CreditCard, { className: "mr-2 h-4 w-4" }),
          /* @__PURE__ */ jsx("span", { children: "Billing" })
        ] })
      ] }) }) }),
      code: `<Command className="rounded-lg border shadow-md">
  <CommandList>
    <CommandGroup>
      <CommandItem>
        <User className="mr-2 h-4 w-4" />
        <span>Profile</span>
      </CommandItem>
      <CommandItem>
        <Settings className="mr-2 h-4 w-4" />
        <span>Settings</span>
      </CommandItem>
    </CommandGroup>
  </CommandList>
</Command>`
    }
  ]
};
const dialogPreview = {
  variants: [
    {
      title: "Default",
      description: "A modal dialog with header, content, and footer",
      preview: /* @__PURE__ */ jsxs(Dialog, { children: [
        /* @__PURE__ */ jsx(DialogTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Open Dialog" }) }),
        /* @__PURE__ */ jsxs(DialogContent, { children: [
          /* @__PURE__ */ jsxs(DialogHeader, { children: [
            /* @__PURE__ */ jsx(DialogTitle, { children: "Edit Profile" }),
            /* @__PURE__ */ jsx(DialogDescription, { children: "Make changes to your profile here. Click save when you're done." })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "grid gap-4 py-4", children: [
            /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-4 items-center gap-4", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "name", className: "text-right text-sm", children: "Name" }),
              /* @__PURE__ */ jsx(
                Input,
                {
                  id: "name",
                  defaultValue: "John Doe",
                  className: "col-span-3"
                }
              )
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-4 items-center gap-4", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "username", className: "text-right text-sm", children: "Username" }),
              /* @__PURE__ */ jsx(
                Input,
                {
                  id: "username",
                  defaultValue: "@johndoe",
                  className: "col-span-3"
                }
              )
            ] })
          ] }),
          /* @__PURE__ */ jsx(DialogFooter, { children: /* @__PURE__ */ jsx(Button, { type: "submit", children: "Save changes" }) })
        ] })
      ] }),
      code: `<Dialog>
  <DialogTrigger asChild>
    <Button variant="outline">Open Dialog</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Edit Profile</DialogTitle>
      <DialogDescription>
        Make changes to your profile here. Click save when you're done.
      </DialogDescription>
    </DialogHeader>
    <div className="grid gap-4 py-4">
      {/* Form content */}
    </div>
    <DialogFooter>
      <Button type="submit">Save changes</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>`
    },
    {
      title: "Confirmation Dialog",
      description: "A simple confirmation dialog with cancel and confirm actions",
      preview: /* @__PURE__ */ jsxs(Dialog, { children: [
        /* @__PURE__ */ jsx(DialogTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "destructive", children: "Delete Account" }) }),
        /* @__PURE__ */ jsxs(DialogContent, { children: [
          /* @__PURE__ */ jsxs(DialogHeader, { children: [
            /* @__PURE__ */ jsx(DialogTitle, { children: "Are you sure?" }),
            /* @__PURE__ */ jsx(DialogDescription, { children: "This action cannot be undone. This will permanently delete your account and remove all your data from our servers." })
          ] }),
          /* @__PURE__ */ jsxs(DialogFooter, { className: "gap-2 sm:gap-0", children: [
            /* @__PURE__ */ jsx(DialogClose, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Cancel" }) }),
            /* @__PURE__ */ jsx(Button, { variant: "destructive", children: "Delete" })
          ] })
        ] })
      ] }),
      code: `<Dialog>
  <DialogTrigger asChild>
    <Button variant="destructive">Delete Account</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Are you sure?</DialogTitle>
      <DialogDescription>
        This action cannot be undone.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter>
      <DialogClose asChild>
        <Button variant="outline">Cancel</Button>
      </DialogClose>
      <Button variant="destructive">Delete</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>`
    }
  ]
};
const dropdownMenuPreview = {
  variants: [
    {
      title: "Default",
      description: "A dropdown menu with grouped items and shortcuts",
      preview: /* @__PURE__ */ jsxs(DropdownMenu, { children: [
        /* @__PURE__ */ jsx(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Open Menu" }) }),
        /* @__PURE__ */ jsxs(DropdownMenuContent, { className: "w-56", children: [
          /* @__PURE__ */ jsx(DropdownMenuLabel, { children: "My Account" }),
          /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
          /* @__PURE__ */ jsxs(DropdownMenuGroup, { children: [
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(User, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Profile" }),
              /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⇧⌘P" })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(CreditCard, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Billing" }),
              /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⌘B" })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(Settings, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Settings" }),
              /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⌘S" })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(Keyboard, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Keyboard shortcuts" }),
              /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⌘K" })
            ] })
          ] }),
          /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
          /* @__PURE__ */ jsxs(DropdownMenuGroup, { children: [
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(Users, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "Team" })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuSub, { children: [
              /* @__PURE__ */ jsxs(DropdownMenuSubTrigger, { children: [
                /* @__PURE__ */ jsx(UserPlus, { className: "mr-2 h-4 w-4" }),
                /* @__PURE__ */ jsx("span", { children: "Invite users" })
              ] }),
              /* @__PURE__ */ jsxs(DropdownMenuSubContent, { children: [
                /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
                  /* @__PURE__ */ jsx(Mail, { className: "mr-2 h-4 w-4" }),
                  /* @__PURE__ */ jsx("span", { children: "Email" })
                ] }),
                /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
                  /* @__PURE__ */ jsx(MessageSquare, { className: "mr-2 h-4 w-4" }),
                  /* @__PURE__ */ jsx("span", { children: "Message" })
                ] }),
                /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
                /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
                  /* @__PURE__ */ jsx(CirclePlus, { className: "mr-2 h-4 w-4" }),
                  /* @__PURE__ */ jsx("span", { children: "More..." })
                ] })
              ] })
            ] }),
            /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
              /* @__PURE__ */ jsx(Plus, { className: "mr-2 h-4 w-4" }),
              /* @__PURE__ */ jsx("span", { children: "New Team" }),
              /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⌘+T" })
            ] })
          ] }),
          /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
          /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
            /* @__PURE__ */ jsx(Github, { className: "mr-2 h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { children: "GitHub" })
          ] }),
          /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
            /* @__PURE__ */ jsx(LifeBuoy, { className: "mr-2 h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { children: "Support" })
          ] }),
          /* @__PURE__ */ jsxs(DropdownMenuItem, { disabled: true, children: [
            /* @__PURE__ */ jsx(Cloud, { className: "mr-2 h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { children: "API" })
          ] }),
          /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
          /* @__PURE__ */ jsxs(DropdownMenuItem, { children: [
            /* @__PURE__ */ jsx(LogOut, { className: "mr-2 h-4 w-4" }),
            /* @__PURE__ */ jsx("span", { children: "Log out" }),
            /* @__PURE__ */ jsx(DropdownMenuShortcut, { children: "⇧⌘Q" })
          ] })
        ] })
      ] }),
      code: `<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="outline">Open Menu</Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent className="w-56">
    <DropdownMenuLabel>My Account</DropdownMenuLabel>
    <DropdownMenuSeparator />
    <DropdownMenuGroup>
      <DropdownMenuItem>
        <User className="mr-2 h-4 w-4" />
        <span>Profile</span>
        <DropdownMenuShortcut>⇧⌘P</DropdownMenuShortcut>
      </DropdownMenuItem>
      {/* More items */}
    </DropdownMenuGroup>
  </DropdownMenuContent>
</DropdownMenu>`
    },
    {
      title: "Simple Menu",
      description: "A simpler dropdown menu without shortcuts",
      preview: /* @__PURE__ */ jsxs(DropdownMenu, { children: [
        /* @__PURE__ */ jsx(DropdownMenuTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Actions" }) }),
        /* @__PURE__ */ jsxs(DropdownMenuContent, { children: [
          /* @__PURE__ */ jsx(DropdownMenuItem, { children: "Edit" }),
          /* @__PURE__ */ jsx(DropdownMenuItem, { children: "Duplicate" }),
          /* @__PURE__ */ jsx(DropdownMenuSeparator, {}),
          /* @__PURE__ */ jsx(DropdownMenuItem, { variant: "destructive", children: "Delete" })
        ] })
      ] }),
      code: `<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="outline" size="sm">Actions</Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuItem>Edit</DropdownMenuItem>
    <DropdownMenuItem>Duplicate</DropdownMenuItem>
    <DropdownMenuSeparator />
    <DropdownMenuItem variant="destructive">Delete</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>`
    }
  ]
};
const emptyStatePreview = {
  variants: [
    {
      title: "Default",
      description: "An empty state with icon, title, and description",
      preview: /* @__PURE__ */ jsx(
        EmptyState,
        {
          icon: /* @__PURE__ */ jsx(Inbox, {}),
          title: "No messages",
          description: "You don't have any messages yet. Start a conversation!"
        }
      ),
      code: `<EmptyState
  icon={<Inbox />}
  title="No messages"
  description="You don't have any messages yet. Start a conversation!"
/>`
    },
    {
      title: "With Action",
      description: "Empty state with a call-to-action button",
      preview: /* @__PURE__ */ jsx(
        EmptyState,
        {
          icon: /* @__PURE__ */ jsx(FileText, {}),
          title: "No documents",
          description: "Get started by creating your first document.",
          children: /* @__PURE__ */ jsx(Button, { children: "Create Document" })
        }
      ),
      code: `<EmptyState
  icon={<FileText />}
  title="No documents"
  description="Get started by creating your first document."
>
  <Button>Create Document</Button>
</EmptyState>`
    },
    {
      title: "Search Results",
      description: "Empty state for no search results",
      preview: /* @__PURE__ */ jsx(
        EmptyState,
        {
          icon: /* @__PURE__ */ jsx(Search, {}),
          title: "No results found",
          description: "Try adjusting your search or filter to find what you're looking for.",
          children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Clear filters" })
        }
      ),
      code: `<EmptyState
  icon={<Search />}
  title="No results found"
  description="Try adjusting your search or filter to find what you're looking for."
>
  <Button variant="outline">Clear filters</Button>
</EmptyState>`
    }
  ]
};
const errorStatePreview = {
  variants: [
    {
      title: "Default",
      description: "A basic error state with an error message",
      preview: /* @__PURE__ */ jsx(ErrorState, { error: "Something went wrong. Please try again later." }),
      code: `<ErrorState error="Something went wrong. Please try again later." />`
    },
    {
      title: "With Title",
      description: "Error state with a title and message",
      preview: /* @__PURE__ */ jsx(
        ErrorState,
        {
          title: "Connection Failed",
          error: "Unable to connect to the server. Please check your internet connection."
        }
      ),
      code: `<ErrorState
  title="Connection Failed"
  error="Unable to connect to the server. Please check your internet connection."
/>`
    },
    {
      title: "Error Object",
      description: "Error state can accept an Error object",
      preview: /* @__PURE__ */ jsx(
        ErrorState,
        {
          title: "Request Failed",
          error: new Error("Network request failed: 500 Internal Server Error")
        }
      ),
      code: `<ErrorState
  title="Request Failed"
  error={new Error("Network request failed: 500 Internal Server Error")}
/>`
    },
    {
      title: "Various Contexts",
      description: "Different error scenarios",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-4", children: [
        /* @__PURE__ */ jsx(ErrorState, { error: "Invalid email address format" }),
        /* @__PURE__ */ jsx(
          ErrorState,
          {
            title: "Authentication Error",
            error: "Your session has expired. Please log in again."
          }
        ),
        /* @__PURE__ */ jsx(
          ErrorState,
          {
            title: "Permission Denied",
            error: "You don't have access to this resource."
          }
        )
      ] }),
      code: `<ErrorState error="Invalid email address format" />
<ErrorState
  title="Authentication Error"
  error="Your session has expired. Please log in again."
/>
<ErrorState
  title="Permission Denied"
  error="You don't have access to this resource."
/>`
    }
  ]
};
const inputPreview = {
  variants: [
    {
      title: "Default",
      description: "A standard text input field",
      preview: /* @__PURE__ */ jsx("div", { className: "w-full max-w-sm", children: /* @__PURE__ */ jsx(Input, { type: "text", placeholder: "Enter text..." }) }),
      code: `<Input type="text" placeholder="Enter text..." />`
    },
    {
      title: "Input Types",
      description: "Different input types for various data",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex w-full max-w-sm flex-col gap-3", children: [
        /* @__PURE__ */ jsx(Input, { type: "email", placeholder: "Email address" }),
        /* @__PURE__ */ jsx(Input, { type: "password", placeholder: "Password" }),
        /* @__PURE__ */ jsx(Input, { type: "number", placeholder: "Number" }),
        /* @__PURE__ */ jsx(Input, { type: "search", placeholder: "Search..." })
      ] }),
      code: `<Input type="email" placeholder="Email address" />
<Input type="password" placeholder="Password" />
<Input type="number" placeholder="Number" />
<Input type="search" placeholder="Search..." />`
    },
    {
      title: "States",
      description: "Disabled and file input states",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex w-full max-w-sm flex-col gap-3", children: [
        /* @__PURE__ */ jsx(Input, { disabled: true, placeholder: "Disabled input" }),
        /* @__PURE__ */ jsx(Input, { type: "file" })
      ] }),
      code: `<Input disabled placeholder="Disabled input" />
<Input type="file" />`
    },
    {
      title: "With Label",
      description: "Input paired with a label for accessibility",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex w-full max-w-sm flex-col gap-2", children: [
        /* @__PURE__ */ jsx("label", { htmlFor: "email", className: "text-sm font-medium", children: "Email" }),
        /* @__PURE__ */ jsx(Input, { id: "email", type: "email", placeholder: "you@example.com" })
      ] }),
      code: `<div className="flex flex-col gap-2">
  <label htmlFor="email" className="text-sm font-medium">
    Email
  </label>
  <Input id="email" type="email" placeholder="you@example.com" />
</div>`
    }
  ]
};
const loadingStatePreview = {
  variants: [
    {
      title: "Size Variants",
      description: "Loading spinners come in different sizes",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-start gap-8", children: [
        /* @__PURE__ */ jsxs("div", { className: "text-center", children: [
          /* @__PURE__ */ jsx(LoadingState, { size: "sm" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-2 text-xs", children: "Small" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "text-center", children: [
          /* @__PURE__ */ jsx(LoadingState, { size: "md" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-2 text-xs", children: "Medium" })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "text-center", children: [
          /* @__PURE__ */ jsx(LoadingState, { size: "lg" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground mt-2 text-xs", children: "Large" })
        ] })
      ] }),
      code: `<LoadingState size="sm" />
<LoadingState size="md" />
<LoadingState size="lg" />`
    },
    {
      title: "With Message",
      description: "Loading state with a descriptive message",
      preview: /* @__PURE__ */ jsx(LoadingState, { size: "md", message: "Loading your data..." }),
      code: `<LoadingState size="md" message="Loading your data..." />`
    },
    {
      title: "Custom Message",
      description: "Different contextual loading messages",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-4", children: [
        /* @__PURE__ */ jsx(LoadingState, { size: "sm", message: "Fetching results..." }),
        /* @__PURE__ */ jsx(LoadingState, { size: "sm", message: "Syncing data..." }),
        /* @__PURE__ */ jsx(LoadingState, { size: "sm", message: "Processing request..." })
      ] }),
      code: `<LoadingState size="sm" message="Fetching results..." />
<LoadingState size="sm" message="Syncing data..." />
<LoadingState size="sm" message="Processing request..." />`
    }
  ]
};
const separatorPreview = {
  variants: [
    {
      title: "Horizontal",
      description: "A horizontal separator dividing content vertically",
      preview: /* @__PURE__ */ jsxs("div", { className: "w-full max-w-md", children: [
        /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
          /* @__PURE__ */ jsx("h4", { className: "text-sm leading-none font-medium", children: "Radix Primitives" }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "An open-source UI component library." })
        ] }),
        /* @__PURE__ */ jsx(Separator, { className: "my-4" }),
        /* @__PURE__ */ jsxs("div", { className: "flex h-5 items-center space-x-4 text-sm", children: [
          /* @__PURE__ */ jsx("div", { children: "Blog" }),
          /* @__PURE__ */ jsx(Separator, { orientation: "vertical" }),
          /* @__PURE__ */ jsx("div", { children: "Docs" }),
          /* @__PURE__ */ jsx(Separator, { orientation: "vertical" }),
          /* @__PURE__ */ jsx("div", { children: "Source" })
        ] })
      ] }),
      code: `<div className="space-y-1">
  <h4 className="text-sm font-medium">Radix Primitives</h4>
  <p className="text-sm text-muted-foreground">
    An open-source UI component library.
  </p>
</div>
<Separator className="my-4" />
<div className="flex h-5 items-center space-x-4 text-sm">
  <div>Blog</div>
  <Separator orientation="vertical" />
  <div>Docs</div>
  <Separator orientation="vertical" />
  <div>Source</div>
</div>`
    },
    {
      title: "Vertical",
      description: "A vertical separator dividing content horizontally",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex h-12 items-center space-x-4", children: [
        /* @__PURE__ */ jsx("span", { className: "text-sm", children: "Item One" }),
        /* @__PURE__ */ jsx(Separator, { orientation: "vertical" }),
        /* @__PURE__ */ jsx("span", { className: "text-sm", children: "Item Two" }),
        /* @__PURE__ */ jsx(Separator, { orientation: "vertical" }),
        /* @__PURE__ */ jsx("span", { className: "text-sm", children: "Item Three" })
      ] }),
      code: `<div className="flex h-12 items-center space-x-4">
  <span className="text-sm">Item One</span>
  <Separator orientation="vertical" />
  <span className="text-sm">Item Two</span>
  <Separator orientation="vertical" />
  <span className="text-sm">Item Three</span>
</div>`
    }
  ]
};
const sheetPreview = {
  variants: [
    {
      title: "Default (Right)",
      description: "A sheet panel that slides in from the right side",
      preview: /* @__PURE__ */ jsxs(Sheet, { children: [
        /* @__PURE__ */ jsx(SheetTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Open Sheet" }) }),
        /* @__PURE__ */ jsxs(SheetContent, { children: [
          /* @__PURE__ */ jsxs(SheetHeader, { children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Edit Profile" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "Make changes to your profile here. Click save when you're done." })
          ] }),
          /* @__PURE__ */ jsxs("div", { className: "grid gap-4 py-4", children: [
            /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-4 items-center gap-4", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "name", className: "text-right text-sm", children: "Name" }),
              /* @__PURE__ */ jsx(
                Input,
                {
                  id: "name",
                  defaultValue: "John Doe",
                  className: "col-span-3"
                }
              )
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "grid grid-cols-4 items-center gap-4", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "username", className: "text-right text-sm", children: "Username" }),
              /* @__PURE__ */ jsx(
                Input,
                {
                  id: "username",
                  defaultValue: "@johndoe",
                  className: "col-span-3"
                }
              )
            ] })
          ] }),
          /* @__PURE__ */ jsx(SheetFooter, { children: /* @__PURE__ */ jsx(SheetClose, { asChild: true, children: /* @__PURE__ */ jsx(Button, { type: "submit", children: "Save changes" }) }) })
        ] })
      ] }),
      code: `<Sheet>
  <SheetTrigger asChild>
    <Button variant="outline">Open Sheet</Button>
  </SheetTrigger>
  <SheetContent>
    <SheetHeader>
      <SheetTitle>Edit Profile</SheetTitle>
      <SheetDescription>
        Make changes to your profile here. Click save when you're done.
      </SheetDescription>
    </SheetHeader>
    <div className="grid gap-4 py-4">
      {/* Form fields */}
    </div>
    <SheetFooter>
      <SheetClose asChild>
        <Button type="submit">Save changes</Button>
      </SheetClose>
    </SheetFooter>
  </SheetContent>
</Sheet>`
    },
    {
      title: "Side Variants",
      description: "Sheets can slide in from any side of the viewport",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-wrap gap-2", children: [
        /* @__PURE__ */ jsxs(Sheet, { children: [
          /* @__PURE__ */ jsx(SheetTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Top" }) }),
          /* @__PURE__ */ jsx(SheetContent, { side: "top", children: /* @__PURE__ */ jsxs(SheetHeader, { children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Top Sheet" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "This sheet slides in from the top." })
          ] }) })
        ] }),
        /* @__PURE__ */ jsxs(Sheet, { children: [
          /* @__PURE__ */ jsx(SheetTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Right" }) }),
          /* @__PURE__ */ jsx(SheetContent, { side: "right", children: /* @__PURE__ */ jsxs(SheetHeader, { children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Right Sheet" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "This sheet slides in from the right." })
          ] }) })
        ] }),
        /* @__PURE__ */ jsxs(Sheet, { children: [
          /* @__PURE__ */ jsx(SheetTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Bottom" }) }),
          /* @__PURE__ */ jsx(SheetContent, { side: "bottom", children: /* @__PURE__ */ jsxs(SheetHeader, { children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Bottom Sheet" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "This sheet slides in from the bottom." })
          ] }) })
        ] }),
        /* @__PURE__ */ jsxs(Sheet, { children: [
          /* @__PURE__ */ jsx(SheetTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Left" }) }),
          /* @__PURE__ */ jsx(SheetContent, { side: "left", children: /* @__PURE__ */ jsxs(SheetHeader, { children: [
            /* @__PURE__ */ jsx(SheetTitle, { children: "Left Sheet" }),
            /* @__PURE__ */ jsx(SheetDescription, { children: "This sheet slides in from the left." })
          ] }) })
        ] })
      ] }),
      code: `<Sheet>
  <SheetTrigger asChild>
    <Button variant="outline">Top</Button>
  </SheetTrigger>
  <SheetContent side="top">
    <SheetHeader>
      <SheetTitle>Top Sheet</SheetTitle>
      <SheetDescription>
        This sheet slides in from the top.
      </SheetDescription>
    </SheetHeader>
  </SheetContent>
</Sheet>

{/* Use side="right" | "bottom" | "left" for other positions */}`
    }
  ]
};
const skeletonPreview = {
  variants: [
    {
      title: "Default",
      description: "Basic skeleton shapes for loading states",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex items-center space-x-4", children: [
        /* @__PURE__ */ jsx(Skeleton, { className: "h-12 w-12 rounded-full" }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
          /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-[250px]" }),
          /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-[200px]" })
        ] })
      ] }),
      code: `<div className="flex items-center space-x-4">
  <Skeleton className="h-12 w-12 rounded-full" />
  <div className="space-y-2">
    <Skeleton className="h-4 w-[250px]" />
    <Skeleton className="h-4 w-[200px]" />
  </div>
</div>`
    },
    {
      title: "Card",
      description: "Skeleton layout for a card component",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-col space-y-3", children: [
        /* @__PURE__ */ jsx(Skeleton, { className: "h-[125px] w-[250px] rounded-xl" }),
        /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
          /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-[250px]" }),
          /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-[200px]" })
        ] })
      ] }),
      code: `<div className="flex flex-col space-y-3">
  <Skeleton className="h-[125px] w-[250px] rounded-xl" />
  <div className="space-y-2">
    <Skeleton className="h-4 w-[250px]" />
    <Skeleton className="h-4 w-[200px]" />
  </div>
</div>`
    },
    {
      title: "Text Lines",
      description: "Skeleton for text content loading",
      preview: /* @__PURE__ */ jsxs("div", { className: "w-full max-w-md space-y-3", children: [
        /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-full" }),
        /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-full" }),
        /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-3/4" })
      ] }),
      code: `<div className="space-y-3">
  <Skeleton className="h-4 w-full" />
  <Skeleton className="h-4 w-full" />
  <Skeleton className="h-4 w-3/4" />
</div>`
    },
    {
      title: "Avatar with Details",
      description: "Common pattern for user profile loading states",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex flex-col gap-4", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ jsx(Skeleton, { className: "h-10 w-10 rounded-full" }),
          /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
            /* @__PURE__ */ jsx(Skeleton, { className: "h-3 w-24" }),
            /* @__PURE__ */ jsx(Skeleton, { className: "h-3 w-32" })
          ] })
        ] }),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
          /* @__PURE__ */ jsx(Skeleton, { className: "h-14 w-14 rounded-lg" }),
          /* @__PURE__ */ jsxs("div", { className: "space-y-1.5", children: [
            /* @__PURE__ */ jsx(Skeleton, { className: "h-4 w-28" }),
            /* @__PURE__ */ jsx(Skeleton, { className: "h-3 w-40" })
          ] })
        ] })
      ] }),
      code: `{/* Small avatar */}
<div className="flex items-center gap-3">
  <Skeleton className="h-10 w-10 rounded-full" />
  <div className="space-y-1.5">
    <Skeleton className="h-3 w-24" />
    <Skeleton className="h-3 w-32" />
  </div>
</div>

{/* Large avatar */}
<div className="flex items-center gap-3">
  <Skeleton className="h-14 w-14 rounded-lg" />
  <div className="space-y-1.5">
    <Skeleton className="h-4 w-28" />
    <Skeleton className="h-3 w-40" />
  </div>
</div>`
    }
  ]
};
const invoices = [
  {
    invoice: "INV001",
    paymentStatus: "Paid",
    totalAmount: "$250.00",
    paymentMethod: "Credit Card"
  },
  {
    invoice: "INV002",
    paymentStatus: "Pending",
    totalAmount: "$150.00",
    paymentMethod: "PayPal"
  },
  {
    invoice: "INV003",
    paymentStatus: "Unpaid",
    totalAmount: "$350.00",
    paymentMethod: "Bank Transfer"
  },
  {
    invoice: "INV004",
    paymentStatus: "Paid",
    totalAmount: "$450.00",
    paymentMethod: "Credit Card"
  },
  {
    invoice: "INV005",
    paymentStatus: "Paid",
    totalAmount: "$550.00",
    paymentMethod: "PayPal"
  }
];
const tablePreview = {
  variants: [
    {
      title: "Default",
      description: "A table with header, body, footer and caption",
      preview: /* @__PURE__ */ jsxs(Table, { children: [
        /* @__PURE__ */ jsx(TableCaption, { children: "A list of your recent invoices." }),
        /* @__PURE__ */ jsx(TableHeader, { children: /* @__PURE__ */ jsxs(TableRow, { children: [
          /* @__PURE__ */ jsx(TableHead, { className: "w-[100px]", children: "Invoice" }),
          /* @__PURE__ */ jsx(TableHead, { children: "Status" }),
          /* @__PURE__ */ jsx(TableHead, { children: "Method" }),
          /* @__PURE__ */ jsx(TableHead, { className: "text-right", children: "Amount" })
        ] }) }),
        /* @__PURE__ */ jsx(TableBody, { children: invoices.map((invoice) => /* @__PURE__ */ jsxs(TableRow, { children: [
          /* @__PURE__ */ jsx(TableCell, { className: "font-medium", children: invoice.invoice }),
          /* @__PURE__ */ jsx(TableCell, { children: invoice.paymentStatus }),
          /* @__PURE__ */ jsx(TableCell, { children: invoice.paymentMethod }),
          /* @__PURE__ */ jsx(TableCell, { className: "text-right", children: invoice.totalAmount })
        ] }, invoice.invoice)) }),
        /* @__PURE__ */ jsx(TableFooter, { children: /* @__PURE__ */ jsxs(TableRow, { children: [
          /* @__PURE__ */ jsx(TableCell, { colSpan: 3, children: "Total" }),
          /* @__PURE__ */ jsx(TableCell, { className: "text-right", children: "$1,750.00" })
        ] }) })
      ] }),
      code: `<Table>
  <TableCaption>A list of your recent invoices.</TableCaption>
  <TableHeader>
    <TableRow>
      <TableHead className="w-[100px]">Invoice</TableHead>
      <TableHead>Status</TableHead>
      <TableHead>Method</TableHead>
      <TableHead className="text-right">Amount</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {invoices.map((invoice) => (
      <TableRow key={invoice.invoice}>
        <TableCell className="font-medium">{invoice.invoice}</TableCell>
        <TableCell>{invoice.paymentStatus}</TableCell>
        <TableCell>{invoice.paymentMethod}</TableCell>
        <TableCell className="text-right">{invoice.totalAmount}</TableCell>
      </TableRow>
    ))}
  </TableBody>
  <TableFooter>
    <TableRow>
      <TableCell colSpan={3}>Total</TableCell>
      <TableCell className="text-right">$1,750.00</TableCell>
    </TableRow>
  </TableFooter>
</Table>`
    },
    {
      title: "Simple Table",
      description: "A basic table without footer or caption",
      preview: /* @__PURE__ */ jsxs(Table, { children: [
        /* @__PURE__ */ jsx(TableHeader, { children: /* @__PURE__ */ jsxs(TableRow, { children: [
          /* @__PURE__ */ jsx(TableHead, { children: "Name" }),
          /* @__PURE__ */ jsx(TableHead, { children: "Email" }),
          /* @__PURE__ */ jsx(TableHead, { children: "Role" })
        ] }) }),
        /* @__PURE__ */ jsxs(TableBody, { children: [
          /* @__PURE__ */ jsxs(TableRow, { children: [
            /* @__PURE__ */ jsx(TableCell, { className: "font-medium", children: "John Doe" }),
            /* @__PURE__ */ jsx(TableCell, { children: "john@example.com" }),
            /* @__PURE__ */ jsx(TableCell, { children: "Admin" })
          ] }),
          /* @__PURE__ */ jsxs(TableRow, { children: [
            /* @__PURE__ */ jsx(TableCell, { className: "font-medium", children: "Jane Smith" }),
            /* @__PURE__ */ jsx(TableCell, { children: "jane@example.com" }),
            /* @__PURE__ */ jsx(TableCell, { children: "Editor" })
          ] }),
          /* @__PURE__ */ jsxs(TableRow, { children: [
            /* @__PURE__ */ jsx(TableCell, { className: "font-medium", children: "Bob Johnson" }),
            /* @__PURE__ */ jsx(TableCell, { children: "bob@example.com" }),
            /* @__PURE__ */ jsx(TableCell, { children: "Viewer" })
          ] })
        ] })
      ] }),
      code: `<Table>
  <TableHeader>
    <TableRow>
      <TableHead>Name</TableHead>
      <TableHead>Email</TableHead>
      <TableHead>Role</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    <TableRow>
      <TableCell className="font-medium">John Doe</TableCell>
      <TableCell>john@example.com</TableCell>
      <TableCell>Admin</TableCell>
    </TableRow>
    {/* More rows */}
  </TableBody>
</Table>`
    }
  ]
};
const tabsPreview = {
  variants: [
    {
      title: "Default",
      description: "Basic tabs with content panels",
      preview: /* @__PURE__ */ jsxs(Tabs, { defaultValue: "account", className: "w-[400px]", children: [
        /* @__PURE__ */ jsxs(TabsList, { children: [
          /* @__PURE__ */ jsx(TabsTrigger, { value: "account", children: "Account" }),
          /* @__PURE__ */ jsx(TabsTrigger, { value: "password", children: "Password" })
        ] }),
        /* @__PURE__ */ jsx(TabsContent, { value: "account", children: /* @__PURE__ */ jsxs(Card, { children: [
          /* @__PURE__ */ jsxs(CardHeader, { children: [
            /* @__PURE__ */ jsx(CardTitle, { children: "Account" }),
            /* @__PURE__ */ jsx(CardDescription, { children: "Make changes to your account here. Click save when you're done." })
          ] }),
          /* @__PURE__ */ jsxs(CardContent, { className: "space-y-2", children: [
            /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "name", className: "text-sm font-medium", children: "Name" }),
              /* @__PURE__ */ jsx(Input, { id: "name", defaultValue: "John Doe" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "username", className: "text-sm font-medium", children: "Username" }),
              /* @__PURE__ */ jsx(Input, { id: "username", defaultValue: "@johndoe" })
            ] })
          ] }),
          /* @__PURE__ */ jsx(CardFooter, { children: /* @__PURE__ */ jsx(Button, { children: "Save changes" }) })
        ] }) }),
        /* @__PURE__ */ jsx(TabsContent, { value: "password", children: /* @__PURE__ */ jsxs(Card, { children: [
          /* @__PURE__ */ jsxs(CardHeader, { children: [
            /* @__PURE__ */ jsx(CardTitle, { children: "Password" }),
            /* @__PURE__ */ jsx(CardDescription, { children: "Change your password here. After saving, you'll be logged out." })
          ] }),
          /* @__PURE__ */ jsxs(CardContent, { className: "space-y-2", children: [
            /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "current", className: "text-sm font-medium", children: "Current password" }),
              /* @__PURE__ */ jsx(Input, { id: "current", type: "password" })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "space-y-1", children: [
              /* @__PURE__ */ jsx("label", { htmlFor: "new", className: "text-sm font-medium", children: "New password" }),
              /* @__PURE__ */ jsx(Input, { id: "new", type: "password" })
            ] })
          ] }),
          /* @__PURE__ */ jsx(CardFooter, { children: /* @__PURE__ */ jsx(Button, { children: "Save password" }) })
        ] }) })
      ] }),
      code: `<Tabs defaultValue="account" className="w-[400px]">
  <TabsList>
    <TabsTrigger value="account">Account</TabsTrigger>
    <TabsTrigger value="password">Password</TabsTrigger>
  </TabsList>
  <TabsContent value="account">
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>Make changes to your account here.</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Form fields */}
      </CardContent>
      <CardFooter>
        <Button>Save changes</Button>
      </CardFooter>
    </Card>
  </TabsContent>
  <TabsContent value="password">
    {/* Password tab content */}
  </TabsContent>
</Tabs>`
    },
    {
      title: "Simple Tabs",
      description: "Tabs with simple text content",
      preview: /* @__PURE__ */ jsxs(Tabs, { defaultValue: "overview", className: "w-[400px]", children: [
        /* @__PURE__ */ jsxs(TabsList, { className: "grid w-full grid-cols-3", children: [
          /* @__PURE__ */ jsx(TabsTrigger, { value: "overview", children: "Overview" }),
          /* @__PURE__ */ jsx(TabsTrigger, { value: "analytics", children: "Analytics" }),
          /* @__PURE__ */ jsx(TabsTrigger, { value: "reports", children: "Reports" })
        ] }),
        /* @__PURE__ */ jsx(TabsContent, { value: "overview", className: "p-4", children: /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Your overview content goes here. This tab shows a summary of your data." }) }),
        /* @__PURE__ */ jsx(TabsContent, { value: "analytics", className: "p-4", children: /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "Analytics content with charts and metrics would appear here." }) }),
        /* @__PURE__ */ jsx(TabsContent, { value: "reports", className: "p-4", children: /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: "View and download your reports from this section." }) })
      ] }),
      code: `<Tabs defaultValue="overview">
  <TabsList className="grid w-full grid-cols-3">
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="analytics">Analytics</TabsTrigger>
    <TabsTrigger value="reports">Reports</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">
    <p>Overview content</p>
  </TabsContent>
  <TabsContent value="analytics">
    <p>Analytics content</p>
  </TabsContent>
  <TabsContent value="reports">
    <p>Reports content</p>
  </TabsContent>
</Tabs>`
    }
  ]
};
const tooltipPreview = {
  variants: [
    {
      title: "Default",
      description: "A simple tooltip that appears on hover",
      preview: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", children: "Hover me" }) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { children: "This is a tooltip" }) })
      ] }),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Hover me</Button>
  </TooltipTrigger>
  <TooltipContent>
    <p>This is a tooltip</p>
  </TooltipContent>
</Tooltip>`
    },
    {
      title: "Positions",
      description: "Tooltips can appear on different sides of the trigger",
      preview: /* @__PURE__ */ jsxs("div", { className: "flex gap-4", children: [
        /* @__PURE__ */ jsxs(Tooltip, { children: [
          /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Top" }) }),
          /* @__PURE__ */ jsx(TooltipContent, { side: "top", children: /* @__PURE__ */ jsx("p", { children: "Top tooltip" }) })
        ] }),
        /* @__PURE__ */ jsxs(Tooltip, { children: [
          /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Right" }) }),
          /* @__PURE__ */ jsx(TooltipContent, { side: "right", children: /* @__PURE__ */ jsx("p", { children: "Right tooltip" }) })
        ] }),
        /* @__PURE__ */ jsxs(Tooltip, { children: [
          /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Bottom" }) }),
          /* @__PURE__ */ jsx(TooltipContent, { side: "bottom", children: /* @__PURE__ */ jsx("p", { children: "Bottom tooltip" }) })
        ] }),
        /* @__PURE__ */ jsxs(Tooltip, { children: [
          /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "sm", children: "Left" }) }),
          /* @__PURE__ */ jsx(TooltipContent, { side: "left", children: /* @__PURE__ */ jsx("p", { children: "Left tooltip" }) })
        ] })
      ] }),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Top</Button>
  </TooltipTrigger>
  <TooltipContent side="top">
    <p>Top tooltip</p>
  </TooltipContent>
</Tooltip>

<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline">Right</Button>
  </TooltipTrigger>
  <TooltipContent side="right">
    <p>Right tooltip</p>
  </TooltipContent>
</Tooltip>`
    },
    {
      title: "With Icon Button",
      description: "Tooltips are commonly used to describe icon-only buttons",
      preview: /* @__PURE__ */ jsxs(Tooltip, { children: [
        /* @__PURE__ */ jsx(TooltipTrigger, { asChild: true, children: /* @__PURE__ */ jsx(Button, { variant: "outline", size: "icon", children: /* @__PURE__ */ jsx(Plus, { className: "h-4 w-4" }) }) }),
        /* @__PURE__ */ jsx(TooltipContent, { children: /* @__PURE__ */ jsx("p", { children: "Add item" }) })
      ] }),
      code: `<Tooltip>
  <TooltipTrigger asChild>
    <Button variant="outline" size="icon">
      <Plus className="h-4 w-4" />
    </Button>
  </TooltipTrigger>
  <TooltipContent>
    <p>Add item</p>
  </TooltipContent>
</Tooltip>`
    }
  ]
};
const componentPreviews = {
  "alert-dialog": alertDialogPreview,
  avatar: avatarPreview,
  badge: badgePreview,
  button: buttonPreview,
  card: cardPreview,
  checkbox: checkboxPreview,
  command: commandPreview,
  dialog: dialogPreview,
  "dropdown-menu": dropdownMenuPreview,
  "empty-state": emptyStatePreview,
  "error-state": errorStatePreview,
  input: inputPreview,
  "loading-state": loadingStatePreview,
  separator: separatorPreview,
  sheet: sheetPreview,
  skeleton: skeletonPreview,
  table: tablePreview,
  tabs: tabsPreview,
  tooltip: tooltipPreview
};
function toDisplayName(name) {
  return name.split(/[-_]/).map((word) => word.charAt(0).toUpperCase() + word.slice(1)).join(" ");
}
function CodeBlock({
  code,
  language: _language = "tsx"
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2e3);
  };
  return /* @__PURE__ */ jsxs("div", { className: "group relative", children: [
    /* @__PURE__ */ jsx("pre", { className: "bg-muted overflow-x-auto rounded-lg border p-4", children: /* @__PURE__ */ jsx("code", { className: "font-mono text-sm", children: code }) }),
    /* @__PURE__ */ jsx(Button, { variant: "ghost", size: "icon-sm", onClick: handleCopy, className: "absolute top-2 right-2 opacity-0 transition-opacity group-hover:opacity-100", children: copied ? /* @__PURE__ */ jsx(Check, { className: "text-primary h-4 w-4" }) : /* @__PURE__ */ jsx(Copy, { className: "h-4 w-4" }) })
  ] });
}
function VariantPreview({
  title,
  description,
  children,
  code
}) {
  return /* @__PURE__ */ jsxs(Card, { className: "overflow-hidden", children: [
    /* @__PURE__ */ jsxs(CardHeader, { className: "border-b", children: [
      /* @__PURE__ */ jsx(CardTitle, { className: "text-base", children: title }),
      description && /* @__PURE__ */ jsx(CardDescription, { children: description })
    ] }),
    /* @__PURE__ */ jsx(CardContent, { className: "bg-muted/30 flex min-h-[120px] items-center justify-center p-6", children: /* @__PURE__ */ jsx("div", { className: "flex flex-wrap items-center gap-4", children }) }),
    /* @__PURE__ */ jsx("div", { className: "border-t", children: /* @__PURE__ */ jsx(CodeBlock, { code }) })
  ] });
}
function ComponentDetailPage() {
  const {
    componentName
  } = Route$6.useParams();
  const component = uiComponents.find((c) => c.name === componentName);
  if (!component) {
    return /* @__PURE__ */ jsx("div", { className: "p-8", children: /* @__PURE__ */ jsxs("div", { className: "py-20 text-center", children: [
      /* @__PURE__ */ jsx("div", { className: "bg-muted mb-4 inline-flex h-16 w-16 items-center justify-center rounded-full", children: /* @__PURE__ */ jsx(Package, { className: "text-muted-foreground h-8 w-8" }) }),
      /* @__PURE__ */ jsx("h3", { className: "text-foreground mb-2 text-xl font-semibold", children: "Component not found" }),
      /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mb-4", children: [
        'The component "',
        componentName,
        `" doesn't exist.`
      ] }),
      /* @__PURE__ */ jsx(Button, { variant: "ghost", asChild: true, children: /* @__PURE__ */ jsxs(Link, { to: "/components", children: [
        /* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }),
        "Back to components"
      ] }) })
    ] }) });
  }
  const displayName = toDisplayName(component.name);
  const previews = componentPreviews[component.name];
  return /* @__PURE__ */ jsxs("div", { className: "p-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "mb-8", children: [
      /* @__PURE__ */ jsx(Button, { variant: "ghost", asChild: true, className: "mb-4", children: /* @__PURE__ */ jsxs(Link, { to: "/components", children: [
        /* @__PURE__ */ jsx(ArrowLeft, { className: "h-4 w-4" }),
        "Back to components"
      ] }) }),
      /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-4", children: [
        /* @__PURE__ */ jsx("div", { className: "bg-muted rounded-xl p-3", children: /* @__PURE__ */ jsx(Package, { className: "text-primary h-8 w-8" }) }),
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h1", { className: "text-foreground text-3xl font-bold", children: displayName }),
          /* @__PURE__ */ jsx("p", { className: "text-muted-foreground font-mono text-sm", children: component.path })
        ] })
      ] })
    ] }),
    component.exports.length > 0 && /* @__PURE__ */ jsxs("div", { className: "mb-8", children: [
      /* @__PURE__ */ jsxs("h2", { className: "text-foreground mb-3 flex items-center gap-2 text-lg font-semibold", children: [
        /* @__PURE__ */ jsx(Code, { className: "text-primary h-5 w-5" }),
        "Exports"
      ] }),
      /* @__PURE__ */ jsx("div", { className: "flex flex-wrap gap-2", children: component.exports.map((exp) => /* @__PURE__ */ jsx(Badge, { variant: "outline", className: "font-mono", children: exp }, exp)) })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "mb-8", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-foreground mb-3 text-lg font-semibold", children: "Import" }),
      /* @__PURE__ */ jsx(CodeBlock, { code: `import { ${component.exports.filter((e) => e !== "default").join(", ")} } from "@/components/ui/${component.name}";` })
    ] }),
    previews ? /* @__PURE__ */ jsxs("div", { className: "space-y-6", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-foreground text-lg font-semibold", children: "Examples" }),
      previews.variants.map((variant, index) => /* @__PURE__ */ jsx(VariantPreview, { title: variant.title, description: variant.description, code: variant.code, children: variant.preview }, index))
    ] }) : /* @__PURE__ */ jsx(Card, { className: "p-8 text-center", children: /* @__PURE__ */ jsxs(CardContent, { className: "pt-0", children: [
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "No preview configuration available for this component yet." }),
      /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mt-2 text-sm", children: [
        "Add a preview file in",
        " ",
        /* @__PURE__ */ jsx("code", { className: "text-primary", children: "src/previews/" })
      ] })
    ] }) })
  ] });
}
export {
  ComponentDetailPage as component
};
