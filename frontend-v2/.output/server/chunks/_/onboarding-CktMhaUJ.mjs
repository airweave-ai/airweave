import { jsx, jsxs, Fragment } from "react/jsx-runtime";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState, useCallback, useEffect, createContext, useContext } from "react";
import { u as useKeyboardShortcut } from "./use-keyboard-shortcut-fo-gRryO.mjs";
import { A as ApiForm } from "./api-form-BOZocKEu.mjs";
import { c as createLucideIcon, u as useAuth0, q as queryKeys, f as fetchOrganizations, X, a as cn, b as authConfig, g as generateOrgSlug, d as createOrganization, e as createCheckoutSession, C as CodeXml, h as Check, B as Button, U as UserAccountDropdown, i as ChevronRight, L as LoaderCircle } from "./router-BGxBdlkD.mjs";
import { I as Input } from "./input-CQnbKF5R.mjs";
import { toast } from "sonner";
import { u as useIsDark } from "./use-is-dark-CmoXbbju.mjs";
import { C as Cloud, U as Users } from "./users.mjs";
import "./tabs-ChSqzczQ.mjs";
import "@radix-ui/react-tabs";
import "@tanstack/react-query-persist-client";
import "@radix-ui/react-slot";
import "class-variance-authority";
import "clsx";
import "tailwind-merge";
import "@radix-ui/react-dialog";
import "@radix-ui/react-tooltip";
import "zustand";
import "zustand/middleware";
import "@radix-ui/react-avatar";
import "@radix-ui/react-dropdown-menu";
import "cmdk";
import "idb-keyval";
const __iconNode$6 = [["path", { d: "m15 18-6-6 6-6", key: "1wnfg3" }]];
const ChevronLeft = createLucideIcon("chevron-left", __iconNode$6);
const __iconNode$5 = [
  ["path", { d: "M12 20v2", key: "1lh1kg" }],
  ["path", { d: "M12 2v2", key: "tus03m" }],
  ["path", { d: "M17 20v2", key: "1rnc9c" }],
  ["path", { d: "M17 2v2", key: "11trls" }],
  ["path", { d: "M2 12h2", key: "1t8f8n" }],
  ["path", { d: "M2 17h2", key: "7oei6x" }],
  ["path", { d: "M2 7h2", key: "asdhe0" }],
  ["path", { d: "M20 12h2", key: "1q8mjw" }],
  ["path", { d: "M20 17h2", key: "1fpfkl" }],
  ["path", { d: "M20 7h2", key: "1o8tra" }],
  ["path", { d: "M7 20v2", key: "4gnj0m" }],
  ["path", { d: "M7 2v2", key: "1i4yhu" }],
  ["rect", { x: "4", y: "4", width: "16", height: "16", rx: "2", key: "1vbyd7" }],
  ["rect", { x: "8", y: "8", width: "8", height: "8", rx: "1", key: "z9xiuo" }]
];
const Cpu = createLucideIcon("cpu", __iconNode$5);
const __iconNode$4 = [
  ["ellipse", { cx: "12", cy: "5", rx: "9", ry: "3", key: "msslwz" }],
  ["path", { d: "M3 5V19A9 3 0 0 0 21 19V5", key: "1wlel7" }],
  ["path", { d: "M3 12A9 3 0 0 0 21 12", key: "mv7ke4" }]
];
const Database = createLucideIcon("database", __iconNode$4);
const __iconNode$3 = [
  ["circle", { cx: "12", cy: "12", r: "10", key: "1mglay" }],
  ["path", { d: "M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20", key: "13o1zl" }],
  ["path", { d: "M2 12h20", key: "9i4pu4" }]
];
const Globe = createLucideIcon("globe", __iconNode$3);
const __iconNode$2 = [
  [
    "path",
    {
      d: "M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z",
      key: "m3kijz"
    }
  ],
  [
    "path",
    {
      d: "m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z",
      key: "1fmvmk"
    }
  ],
  ["path", { d: "M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0", key: "1f8sc4" }],
  ["path", { d: "M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5", key: "qeys4" }]
];
const Rocket = createLucideIcon("rocket", __iconNode$2);
const __iconNode$1 = [
  [
    "path",
    {
      d: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      key: "oel41y"
    }
  ]
];
const Shield = createLucideIcon("shield", __iconNode$1);
const __iconNode = [
  [
    "path",
    {
      d: "M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z",
      key: "1s2grr"
    }
  ],
  ["path", { d: "M20 2v4", key: "1rf3ol" }],
  ["path", { d: "M22 4h-4", key: "gwowj6" }],
  ["circle", { cx: "4", cy: "20", r: "2", key: "6kqj1y" }]
];
const Sparkles = createLucideIcon("sparkles", __iconNode);
function useBeforeUnload(shouldWarn) {
  useEffect(() => {
    const handleBeforeUnload = (event) => {
      const warn = typeof shouldWarn === "function" ? shouldWarn() : shouldWarn;
      if (warn) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [shouldWarn]);
}
const StepsContext = createContext(null);
function useStepsContext() {
  const context = useContext(StepsContext);
  if (!context) {
    throw new Error("Steps compound components must be used within Steps");
  }
  return context;
}
function Steps({
  currentStep,
  onStepChange,
  totalSteps,
  children,
  className
}) {
  const goToStep = (step) => {
    if (step >= 1 && step <= totalSteps) {
      onStepChange(step);
    }
  };
  const nextStep = () => goToStep(currentStep + 1);
  const prevStep = () => goToStep(currentStep - 1);
  return /* @__PURE__ */ jsx(
    StepsContext.Provider,
    {
      value: {
        currentStep,
        totalSteps,
        goToStep,
        nextStep,
        prevStep,
        isFirstStep: currentStep === 1,
        isLastStep: currentStep === totalSteps
      },
      children: /* @__PURE__ */ jsx("div", { className: cn("w-full", className), children })
    }
  );
}
function StepsIndicator({ className }) {
  const { currentStep, totalSteps } = useStepsContext();
  return /* @__PURE__ */ jsx("div", { className: cn("flex items-center gap-2", className), children: Array.from({ length: totalSteps }, (_, i) => {
    const stepNumber = i + 1;
    const isCompleted = stepNumber < currentStep;
    const isCurrent = stepNumber === currentStep;
    return /* @__PURE__ */ jsx(
      "div",
      {
        className: cn(
          "h-1.5 rounded-full transition-all duration-300",
          isCompleted ? "bg-primary w-6" : isCurrent ? "bg-primary w-12" : "bg-muted w-6"
        )
      },
      i
    );
  }) });
}
function StepsCounter({ className }) {
  const { currentStep, totalSteps } = useStepsContext();
  return /* @__PURE__ */ jsxs("span", { className: cn("text-muted-foreground text-sm", className), children: [
    "Step ",
    currentStep,
    " of ",
    totalSteps
  ] });
}
function StepContent({ step, children, className }) {
  const { currentStep } = useStepsContext();
  if (step !== currentStep) return null;
  return /* @__PURE__ */ jsx(
    "div",
    {
      className: cn(
        "animate-in fade-in-0 slide-in-from-right-4 duration-300",
        className
      ),
      children
    }
  );
}
function StepsNavigation({ children, className }) {
  return /* @__PURE__ */ jsx("div", { className: cn("flex items-center justify-between", className), children });
}
Steps.Indicator = StepsIndicator;
Steps.Counter = StepsCounter;
Steps.Content = StepContent;
Steps.Navigation = StepsNavigation;
const ORGANIZATION_SIZES = [
  { value: "1", label: "1", description: "Solo" },
  { value: "2-5", label: "2-5", description: "Small team" },
  { value: "6-20", label: "6-20", description: "Growing startup" },
  { value: "21-100", label: "21-100", description: "Scale-up" },
  { value: "101-500", label: "101-500", description: "Mid-market" },
  { value: "500+", label: "500+", description: "Enterprise" }
];
const USER_ROLES = [
  { value: "founder", label: "Founder/CEO", icon: Sparkles },
  { value: "engineering", label: "Engineering", icon: CodeXml },
  { value: "data", label: "Data/AI", icon: Database },
  { value: "product", label: "Product", icon: Rocket },
  { value: "devops", label: "DevOps", icon: Cloud },
  { value: "other", label: "Other", icon: Users }
];
const ORGANIZATION_TYPES = [
  {
    value: "ai_startup",
    label: "AI/ML Startup",
    icon: Cpu,
    description: "Building AI-powered products"
  },
  {
    value: "saas",
    label: "SaaS Platform",
    icon: Cloud,
    description: "Cloud-based software services"
  },
  {
    value: "data_platform",
    label: "Data Platform",
    icon: Database,
    description: "Data infrastructure & analytics"
  },
  {
    value: "dev_tools",
    label: "Developer Tools",
    icon: CodeXml,
    description: "Tools for developers"
  },
  {
    value: "fintech",
    label: "Fintech",
    icon: Shield,
    description: "Financial technology"
  },
  {
    value: "other",
    label: "Other",
    icon: Globe,
    description: "Other industries"
  }
];
const SUBSCRIPTION_PLANS = [
  {
    value: "developer",
    label: "Developer",
    price: "Free",
    period: "",
    description: "Perfect for personal agents and side projects. No credit card required.",
    features: [
      "10 source connections",
      "500 queries / mo",
      "50K entities / mo",
      "1 team member",
      "Community support"
    ],
    teamMemberLimit: 1,
    recommended: false
  },
  {
    value: "pro",
    label: "Pro",
    price: "$20",
    yearlyPrice: "$16",
    period: "per month",
    description: "Take your agent to the next level",
    features: [
      "50 source connections",
      "2K queries / mo",
      "100K entities / mo",
      "2 team members",
      "Email support"
    ],
    teamMemberLimit: 2,
    recommended: true
  },
  {
    value: "team",
    label: "Team",
    price: "$299",
    yearlyPrice: "$239",
    period: "per month",
    description: "For fast-moving teams that need scale and control",
    features: [
      "1000 source connections",
      "10K queries / mo",
      "1M entities synced / mo",
      "10 team members",
      "Dedicated Slack support",
      "Dedicated onboarding"
    ],
    teamMemberLimit: 10,
    recommended: false
  },
  {
    value: "enterprise",
    label: "Enterprise",
    price: "Custom",
    period: "",
    description: "Tailored solutions for large organizations",
    features: [
      "Unlimited source connections",
      "Custom usage limits",
      "Tailored onboarding",
      "Dedicated priority support",
      "Custom integrations (Optional)",
      "On-premise deployment (Optional)",
      "SLAs (Optional)"
    ],
    teamMemberLimit: 1e3,
    recommended: false
  }
];
const DEFAULT_ONBOARDING_DATA = {
  organizationName: "",
  organizationSize: "",
  userRole: "",
  organizationType: "",
  subscriptionPlan: "pro",
  teamMembers: [],
  billingPeriod: "monthly"
};
function StepOrgName({ value, onChange, onKeyPress }) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "What should we call your organization?" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Choose a name that represents your team or company" })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-3", children: [
      /* @__PURE__ */ jsx(
        Input,
        {
          type: "text",
          placeholder: "e.g., Acme AI",
          value,
          onChange: (e) => onChange(e.target.value),
          onKeyDown: onKeyPress,
          className: cn(
            "w-full px-4 py-3 text-lg",
            "placeholder:text-muted-foreground/50"
          ),
          autoFocus: true
        }
      ),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: "Use letters, numbers, spaces, hyphens, and underscores only - You can always change this later" })
    ] })
  ] });
}
function StepOrgSize({ value, onChange }) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "How many people are in your organization?" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "This helps us recommend the right plan" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "grid grid-cols-3 gap-3", children: ORGANIZATION_SIZES.map((size) => /* @__PURE__ */ jsxs(
      "button",
      {
        type: "button",
        onClick: () => onChange(size.value),
        className: cn(
          "rounded-lg border p-6 text-center transition-all",
          "hover:border-primary/50",
          value === size.value ? "border-primary bg-primary/5" : "border-border"
        ),
        children: [
          /* @__PURE__ */ jsx("div", { className: "mb-1 text-2xl font-light", children: size.label }),
          /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-xs", children: size.description })
        ]
      },
      size.value
    )) })
  ] });
}
function StepOrgType({ value, onChange }) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "What type of company are you?" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "This helps us understand your data integration needs" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "grid grid-cols-2 gap-4", children: ORGANIZATION_TYPES.map((type) => {
      const Icon = type.icon;
      return /* @__PURE__ */ jsx(
        "button",
        {
          type: "button",
          onClick: () => onChange(type.value),
          className: cn(
            "group rounded-lg border p-6 text-left transition-all",
            "hover:border-primary/50",
            value === type.value ? "border-primary bg-primary/5" : "border-border"
          ),
          children: /* @__PURE__ */ jsxs("div", { className: "flex items-start space-x-4", children: [
            /* @__PURE__ */ jsx(
              Icon,
              {
                className: cn(
                  "mt-0.5 h-6 w-6 flex-shrink-0 transition-colors",
                  value === type.value ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                )
              }
            ),
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx("div", { className: "mb-1 font-medium", children: type.label }),
              /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-xs", children: type.description })
            ] })
          ] })
        },
        type.value
      );
    }) })
  ] });
}
function StepSubscription({
  value,
  onChange,
  billingPeriod,
  onBillingPeriodChange,
  authEnabled = true
}) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "Choose your plan" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "You can always upgrade or downgrade later" }),
      !authEnabled && /* @__PURE__ */ jsx("div", { className: "mt-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3", children: /* @__PURE__ */ jsxs("p", { className: "text-xs text-amber-600 dark:text-amber-400", children: [
        /* @__PURE__ */ jsx("strong", { children: "Local Development Mode:" }),
        " Billing is disabled. You'll go straight to the dashboard after setup."
      ] }) })
    ] }),
    authEnabled && /* @__PURE__ */ jsx("div", { className: "relative flex justify-center", children: /* @__PURE__ */ jsxs("div", { className: "relative", children: [
      /* @__PURE__ */ jsxs("div", { className: "bg-muted relative inline-flex items-center rounded-lg border p-1 shadow-sm", children: [
        /* @__PURE__ */ jsx(
          "div",
          {
            className: cn(
              "bg-blue/20 absolute top-1 h-[calc(100%-8px)] rounded-md shadow-sm transition-all duration-200",
              billingPeriod === "monthly" ? "left-1 w-[80px]" : "left-[80px] w-[140px]"
            )
          }
        ),
        /* @__PURE__ */ jsx(
          "button",
          {
            type: "button",
            onClick: () => onBillingPeriodChange("monthly"),
            className: cn(
              "relative z-10 w-[80px] rounded-md px-4 py-2 text-sm transition-all",
              billingPeriod === "monthly" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            ),
            children: "Monthly"
          }
        ),
        /* @__PURE__ */ jsxs(
          "button",
          {
            type: "button",
            onClick: () => onBillingPeriodChange("yearly"),
            className: cn(
              "relative z-10 flex w-[140px] items-center justify-center gap-2 rounded-md px-4 py-2 text-sm transition-all",
              billingPeriod === "yearly" ? "text-foreground" : "text-muted-foreground hover:text-foreground"
            ),
            children: [
              "Yearly",
              /* @__PURE__ */ jsx("span", { className: "bg-primary/10 text-primary rounded px-1.5 py-0.5 text-xs", children: "Save 20%" })
            ]
          }
        )
      ] }),
      /* @__PURE__ */ jsx(
        "div",
        {
          className: cn(
            "absolute top-full left-1/2 mt-1 -translate-x-1/2 transition-opacity duration-200",
            billingPeriod === "yearly" ? "opacity-100" : "pointer-events-none opacity-0"
          ),
          children: /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-center text-xs whitespace-nowrap", children: "After 12 months, your plan will renew at monthly rates." })
        }
      )
    ] }) }),
    /* @__PURE__ */ jsx("div", { className: "grid gap-4", children: SUBSCRIPTION_PLANS.map((plan) => /* @__PURE__ */ jsxs(
      "button",
      {
        type: "button",
        onClick: () => {
          if (plan.value === "enterprise") {
            window.open(
              "https://cal.com/lennert-airweave/airweave-demo",
              "_blank",
              "noopener,noreferrer"
            );
            return;
          }
          onChange(plan.value);
        },
        className: cn(
          "relative rounded-lg border p-6 text-left transition-all",
          "hover:border-primary/50",
          value === plan.value ? "border-primary bg-primary/5" : "border-border"
        ),
        children: [
          /* @__PURE__ */ jsxs("div", { className: "mb-4 flex items-start justify-between", children: [
            /* @__PURE__ */ jsxs("div", { children: [
              /* @__PURE__ */ jsx("div", { className: "mb-1 flex items-center gap-2", children: /* @__PURE__ */ jsx("h3", { className: "text-lg font-medium", children: plan.label }) }),
              /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-sm", children: plan.description })
            ] }),
            /* @__PURE__ */ jsxs("div", { className: "text-right", children: [
              /* @__PURE__ */ jsx("div", { className: "text-2xl font-light", children: !authEnabled ? "Free" : billingPeriod === "yearly" && plan.yearlyPrice ? plan.yearlyPrice : plan.price }),
              plan.period && !authEnabled && /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-xs", children: "local dev" }),
              plan.period && authEnabled && /* @__PURE__ */ jsx("div", { className: "text-muted-foreground text-xs", children: billingPeriod === "yearly" && plan.yearlyPrice ? "per month (billed yearly)" : plan.period }),
              plan.recommended && /* @__PURE__ */ jsx("div", { className: "text-primary mt-1 text-xs", children: "Recommended" })
            ] })
          ] }),
          /* @__PURE__ */ jsx("div", { className: "text-muted-foreground grid grid-cols-2 gap-x-4 gap-y-2 text-xs", children: plan.features.map((feature, index) => /* @__PURE__ */ jsxs("div", { className: "flex items-center", children: [
            /* @__PURE__ */ jsx(Check, { className: "text-primary mr-2 h-3 w-3 flex-shrink-0" }),
            feature
          ] }, index)) })
        ]
      },
      plan.value
    )) })
  ] });
}
function StepTeamInvites({
  teamMembers,
  onChange,
  subscriptionPlan,
  currentUserEmail
}) {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [emailError, setEmailError] = useState("");
  const currentPlanLimit = SUBSCRIPTION_PLANS.find((plan) => plan.value === subscriptionPlan)?.teamMemberLimit || 2;
  const validateEmail = useCallback(
    (email) => {
      if (!email) {
        setEmailError("");
        return false;
      }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        setEmailError("Please enter a valid email address");
        return false;
      }
      if (currentUserEmail && email.toLowerCase() === currentUserEmail.toLowerCase()) {
        setEmailError(
          "You don't need to invite yourself - you'll be the owner"
        );
        return false;
      }
      const existingMember = teamMembers.find(
        (member) => member.email.toLowerCase() === email.toLowerCase()
      );
      if (existingMember) {
        setEmailError("This email has already been added");
        return false;
      }
      if (teamMembers.length >= currentPlanLimit - 1) {
        setEmailError(
          `You've reached the maximum team size for the ${subscriptionPlan} plan`
        );
        return false;
      }
      setEmailError("");
      return true;
    },
    [teamMembers, currentPlanLimit, subscriptionPlan, currentUserEmail]
  );
  const handleEmailChange = (e) => {
    const email = e.target.value;
    setInviteEmail(email);
    if (!email) {
      setEmailError("");
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (emailRegex.test(email)) {
      validateEmail(email);
    } else {
      setEmailError("");
    }
  };
  const handleAddTeamMember = () => {
    if (!validateEmail(inviteEmail)) return;
    const newMember = {
      email: inviteEmail,
      role: inviteRole
    };
    onChange([...teamMembers, newMember]);
    setInviteEmail("");
    setInviteRole("member");
    setEmailError("");
  };
  const handleRemoveTeamMember = (email) => {
    onChange(teamMembers.filter((member) => member.email !== email));
  };
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && inviteEmail && !emailError) {
      e.preventDefault();
      handleAddTeamMember();
    }
  };
  const isValidEmail = inviteEmail && !emailError && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteEmail);
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "Invite your team" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "Get your team onboard from day one" })
    ] }),
    /* @__PURE__ */ jsxs("div", { className: "space-y-4", children: [
      /* @__PURE__ */ jsxs("div", { children: [
        /* @__PURE__ */ jsx("h3", { className: "text-foreground text-sm font-medium", children: "Add team members" }),
        /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mt-0.5 text-xs", children: [
          "Your ",
          subscriptionPlan,
          " plan includes up to ",
          currentPlanLimit,
          " team members"
        ] })
      ] }),
      /* @__PURE__ */ jsx("div", { className: "space-y-3", children: /* @__PURE__ */ jsxs("div", { className: "flex gap-3", children: [
        /* @__PURE__ */ jsxs("div", { className: "flex-1", children: [
          /* @__PURE__ */ jsx(
            Input,
            {
              type: "email",
              placeholder: "Email address",
              value: inviteEmail,
              onChange: handleEmailChange,
              onBlur: () => validateEmail(inviteEmail),
              onKeyDown: handleKeyPress,
              className: cn(
                "h-8 px-3 text-sm",
                emailError && inviteEmail && "border-destructive/50",
                teamMembers.length >= currentPlanLimit - 1 && "cursor-not-allowed opacity-50"
              ),
              disabled: teamMembers.length >= currentPlanLimit - 1
            }
          ),
          emailError && inviteEmail && /* @__PURE__ */ jsx("p", { className: "text-destructive/80 mt-1 text-xs", children: emailError })
        ] }),
        /* @__PURE__ */ jsxs(
          "select",
          {
            value: inviteRole,
            onChange: (e) => setInviteRole(e.target.value),
            className: cn(
              "h-8 w-24 rounded-md border bg-transparent px-2 text-sm",
              "focus:border-border focus:ring-0 focus:outline-none",
              "transition-colors",
              teamMembers.length >= currentPlanLimit - 1 && "cursor-not-allowed opacity-50"
            ),
            disabled: teamMembers.length >= currentPlanLimit - 1,
            children: [
              /* @__PURE__ */ jsx("option", { value: "member", children: "Member" }),
              /* @__PURE__ */ jsx("option", { value: "admin", children: "Admin" })
            ]
          }
        ),
        /* @__PURE__ */ jsx(
          Button,
          {
            type: "button",
            size: "sm",
            onClick: handleAddTeamMember,
            disabled: !isValidEmail || teamMembers.length >= currentPlanLimit - 1,
            className: "h-8",
            children: "Add"
          }
        )
      ] }) }),
      teamMembers.length > 0 && /* @__PURE__ */ jsxs("div", { className: "mt-6 space-y-4", children: [
        /* @__PURE__ */ jsxs("div", { children: [
          /* @__PURE__ */ jsx("h3", { className: "text-foreground pt-2 text-sm font-medium", children: "Team members to invite" }),
          /* @__PURE__ */ jsxs("p", { className: "text-muted-foreground mt-0.5 text-xs", children: [
            teamMembers.length,
            " of ",
            currentPlanLimit - 1,
            " team members added"
          ] })
        ] }),
        /* @__PURE__ */ jsx("div", { className: "border-border divide-border divide-y rounded-lg border", children: teamMembers.map((member, index) => /* @__PURE__ */ jsxs(
          "div",
          {
            className: "flex items-center justify-between px-4 py-2",
            children: [
              /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-3", children: [
                /* @__PURE__ */ jsx("div", { className: "text-sm", children: member.email }),
                /* @__PURE__ */ jsx(
                  "span",
                  {
                    className: cn(
                      "rounded-full px-2 py-0.5 text-xs",
                      member.role === "admin" ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
                    ),
                    children: member.role
                  }
                )
              ] }),
              /* @__PURE__ */ jsx(
                "button",
                {
                  type: "button",
                  onClick: () => handleRemoveTeamMember(member.email),
                  className: "text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded p-1 transition-colors",
                  children: /* @__PURE__ */ jsx(X, { className: "h-3.5 w-3.5" })
                }
              )
            ]
          },
          index
        )) })
      ] })
    ] })
  ] });
}
function StepUserRole({ value, onChange }) {
  return /* @__PURE__ */ jsxs("div", { className: "space-y-8", children: [
    /* @__PURE__ */ jsxs("div", { className: "space-y-2", children: [
      /* @__PURE__ */ jsx("h2", { className: "text-2xl font-normal", children: "What's your role?" }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground", children: "We'll customize your experience based on your needs" })
    ] }),
    /* @__PURE__ */ jsx("div", { className: "grid grid-cols-3 gap-3", children: USER_ROLES.map((role) => {
      const Icon = role.icon;
      return /* @__PURE__ */ jsxs(
        "button",
        {
          type: "button",
          onClick: () => onChange(role.value),
          className: cn(
            "group rounded-lg border p-6 text-center transition-all",
            "hover:border-primary/50",
            value === role.value ? "border-primary bg-primary/5" : "border-border"
          ),
          children: [
            /* @__PURE__ */ jsx(
              Icon,
              {
                className: cn(
                  "mx-auto mb-3 h-8 w-8 transition-colors",
                  value === role.value ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
                )
              }
            ),
            /* @__PURE__ */ jsx("div", { className: "text-sm", children: role.label })
          ]
        },
        role.value
      );
    }) })
  ] });
}
function useCreateOrganization(formData) {
  const navigate = useNavigate();
  const { getAccessTokenSilently } = useAuth0();
  return useMutation({
    mutationFn: async () => {
      const token = await getAccessTokenSilently();
      const org_metadata = {
        onboarding: {
          organizationSize: formData.organizationSize,
          userRole: formData.userRole,
          organizationType: formData.organizationType,
          subscriptionPlan: formData.subscriptionPlan,
          teamInvites: formData.teamMembers,
          completedAt: (/* @__PURE__ */ new Date()).toISOString()
        }
      };
      const organization = await createOrganization(token, {
        name: formData.organizationName,
        description: `${formData.organizationType} company with ${formData.organizationSize} people`,
        org_metadata
      });
      if (!authConfig.authEnabled) {
        return { organization, redirectUrl: null };
      }
      if (formData.subscriptionPlan === "developer") {
        return { organization, redirectUrl: null };
      }
      try {
        const isEligibleForYearly = ["pro", "team"].includes(
          formData.subscriptionPlan
        );
        const yearly = formData.billingPeriod === "yearly" && isEligibleForYearly;
        const { checkout_url } = await createCheckoutSession(
          token,
          {
            plan: formData.subscriptionPlan,
            success_url: `${window.location.origin}/billing/success?session_id={CHECKOUT_SESSION_ID}`,
            cancel_url: `${window.location.origin}/billing/cancel`
          },
          yearly
        );
        return { organization, redirectUrl: checkout_url };
      } catch {
        console.warn("Billing setup failed, but organization was created");
        return { organization, redirectUrl: null };
      }
    },
    onSuccess: ({ organization, redirectUrl }) => {
      if (redirectUrl) {
        window.location.href = redirectUrl;
      } else {
        toast.success("Organization created successfully!");
        navigate({
          to: "/$orgSlug",
          params: { orgSlug: generateOrgSlug(organization) }
        });
      }
    },
    onError: (error) => {
      toast.error("Failed to complete setup. Please try again.", {
        description: error.message
      });
    }
  });
}
function validateOrgName(name) {
  const trimmed = name.trim();
  if (trimmed.length < 4) {
    return "Organization name must be at least 4 characters long";
  }
  const safeCharRegex = /^[a-zA-Z0-9\s\-_]+$/;
  if (!safeCharRegex.test(trimmed)) {
    return "Organization name can only contain letters, numbers, spaces, hyphens, and underscores";
  }
  if (trimmed.includes("  ")) {
    return "Organization name cannot contain consecutive spaces";
  }
  if (trimmed.startsWith(" ") || trimmed.endsWith(" ")) {
    return "Organization name cannot start or end with spaces";
  }
  return null;
}
function useOnboardingValidation({
  formData,
  currentStep
}) {
  const isStepValid = useCallback(() => {
    switch (currentStep) {
      case 1:
        return formData.organizationName.trim().length > 0;
      case 2:
        return formData.organizationSize !== "";
      case 3:
        return formData.userRole !== "";
      case 4:
        return formData.organizationType !== "";
      case 5:
        return formData.subscriptionPlan !== "";
      case 6:
        return true;
      // Team invites are optional
      default:
        return false;
    }
  }, [currentStep, formData]);
  const validateAndProceed = useCallback(() => {
    if (currentStep === 1) {
      const error = validateOrgName(formData.organizationName);
      if (error) {
        toast.error(error);
        return false;
      }
    }
    return isStepValid();
  }, [currentStep, formData.organizationName, isStepValid]);
  return {
    isStepValid: isStepValid(),
    validateAndProceed
  };
}
const TOTAL_STEPS = 6;
function OnboardingPage() {
  const navigate = useNavigate();
  const isDark = useIsDark();
  const {
    user,
    getAccessTokenSilently
  } = useAuth0();
  const [currentStep, setCurrentStep] = useState(1);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [formData, setFormData] = useState(DEFAULT_ONBOARDING_DATA);
  const {
    data: organizations = []
  } = useQuery({
    queryKey: queryKeys.organizations.all,
    queryFn: async () => {
      const token = await getAccessTokenSilently();
      return fetchOrganizations(token);
    }
  });
  const hasOrganizations = organizations.length > 0;
  const createOrgMutation = useCreateOrganization(formData);
  const {
    isStepValid,
    validateAndProceed
  } = useOnboardingValidation({
    formData,
    currentStep
  });
  useKeyboardShortcut({
    key: "Escape",
    onKeyDown: () => navigate({
      to: "/"
    }),
    enabled: hasOrganizations
  });
  useBeforeUnload(!hasOrganizations);
  const updateFormData = useCallback((field, value) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value
    }));
  }, []);
  const handleNext = () => {
    if (!validateAndProceed()) return;
    if (currentStep < TOTAL_STEPS) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep((prev) => prev + 1);
        setIsTransitioning(false);
      }, 150);
    }
  };
  const handleBack = () => {
    if (currentStep > 1) {
      setIsTransitioning(true);
      setTimeout(() => {
        setCurrentStep((prev) => prev - 1);
        setIsTransitioning(false);
      }, 150);
    }
  };
  const handleComplete = () => {
    createOrgMutation.mutate();
  };
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && isStepValid) {
      e.preventDefault();
      if (!validateAndProceed()) return;
      if (currentStep < TOTAL_STEPS) {
        handleNext();
      } else {
        handleComplete();
      }
    }
  };
  const handleSelection = (field, value) => {
    updateFormData(field, value);
    if (currentStep >= 2 && currentStep <= 5) {
      setTimeout(() => {
        setIsTransitioning(true);
        setTimeout(() => {
          setCurrentStep((prev) => prev + 1);
          setIsTransitioning(false);
        }, 150);
      }, 200);
    }
  };
  const apiRequestBody = {
    name: formData.organizationName,
    description: `${formData.organizationType} company with ${formData.organizationSize} people`,
    org_metadata: {
      onboarding: {
        organizationSize: formData.organizationSize,
        userRole: formData.userRole,
        organizationType: formData.organizationType,
        subscriptionPlan: formData.subscriptionPlan,
        teamInvites: formData.teamMembers
      }
    }
  };
  return /* @__PURE__ */ jsx("div", { className: "bg-background flex min-h-screen items-center justify-center p-4 py-12", children: /* @__PURE__ */ jsxs("div", { className: "relative w-full max-w-2xl", children: [
    /* @__PURE__ */ jsxs("div", { className: "mb-12 text-center", children: [
      /* @__PURE__ */ jsx("img", { src: isDark ? "/airweave-logo-svg-white-darkbg.svg" : "/airweave-logo-svg-lightbg-blacklogo.svg", alt: "Airweave", className: "mx-auto mb-2 h-8 w-auto", style: {
        maxWidth: "180px"
      } }),
      /* @__PURE__ */ jsx("p", { className: "text-muted-foreground text-xs", children: "Build smarter agents" })
    ] }),
    /* @__PURE__ */ jsxs(Steps, { currentStep, onStepChange: setCurrentStep, totalSteps: TOTAL_STEPS, children: [
      /* @__PURE__ */ jsxs("div", { className: "mb-8 flex items-center justify-between", children: [
        /* @__PURE__ */ jsx(Steps.Indicator, {}),
        /* @__PURE__ */ jsxs("div", { className: "flex items-center gap-4", children: [
          /* @__PURE__ */ jsx(Steps.Counter, {}),
          hasOrganizations && /* @__PURE__ */ jsx("button", { onClick: () => navigate({
            to: "/"
          }), className: "hover:bg-muted/50 rounded-lg p-2 transition-colors", title: "Close", children: /* @__PURE__ */ jsx(X, { className: "h-4 w-4" }) })
        ] })
      ] }),
      /* @__PURE__ */ jsxs("div", { className: cn("min-h-[400px] transition-opacity duration-150", isTransitioning ? "opacity-0" : "opacity-100"), children: [
        /* @__PURE__ */ jsx(Steps.Content, { step: 1, children: /* @__PURE__ */ jsx(StepOrgName, { value: formData.organizationName, onChange: (value) => updateFormData("organizationName", value), onKeyPress: handleKeyPress }) }),
        /* @__PURE__ */ jsx(Steps.Content, { step: 2, children: /* @__PURE__ */ jsx(StepOrgSize, { value: formData.organizationSize, onChange: (value) => handleSelection("organizationSize", value) }) }),
        /* @__PURE__ */ jsx(Steps.Content, { step: 3, children: /* @__PURE__ */ jsx(StepUserRole, { value: formData.userRole, onChange: (value) => handleSelection("userRole", value) }) }),
        /* @__PURE__ */ jsx(Steps.Content, { step: 4, children: /* @__PURE__ */ jsx(StepOrgType, { value: formData.organizationType, onChange: (value) => handleSelection("organizationType", value) }) }),
        /* @__PURE__ */ jsx(Steps.Content, { step: 5, children: /* @__PURE__ */ jsx(StepSubscription, { value: formData.subscriptionPlan, onChange: (value) => handleSelection("subscriptionPlan", value), billingPeriod: formData.billingPeriod, onBillingPeriodChange: (period) => updateFormData("billingPeriod", period), authEnabled: authConfig.authEnabled }) }),
        /* @__PURE__ */ jsx(Steps.Content, { step: 6, children: /* @__PURE__ */ jsxs(ApiForm, { method: "POST", endpoint: "/organizations", body: apiRequestBody, onBodyChange: (newBody) => {
          if (typeof newBody.name === "string") {
            updateFormData("organizationName", newBody.name);
          }
        }, children: [
          /* @__PURE__ */ jsx(ApiForm.Toggle, { className: "mb-4" }),
          /* @__PURE__ */ jsx(ApiForm.FormView, { children: /* @__PURE__ */ jsx(StepTeamInvites, { teamMembers: formData.teamMembers, onChange: (members) => updateFormData("teamMembers", members), subscriptionPlan: formData.subscriptionPlan, currentUserEmail: user?.email }) }),
          /* @__PURE__ */ jsx(ApiForm.CodeView, {})
        ] }) })
      ] }),
      /* @__PURE__ */ jsx(OnboardingNavigation, { currentStep, totalSteps: TOTAL_STEPS, isStepValid, isCreating: createOrgMutation.isPending, authEnabled: authConfig.authEnabled, onBack: handleBack, onNext: handleNext, onComplete: handleComplete })
    ] })
  ] }) });
}
function OnboardingNavigation({
  currentStep,
  totalSteps,
  isStepValid,
  isCreating,
  authEnabled,
  onBack,
  onNext,
  onComplete
}) {
  return /* @__PURE__ */ jsxs("div", { className: "relative mt-12 flex items-center justify-between", children: [
    currentStep > 1 && /* @__PURE__ */ jsxs(Button, { variant: "ghost", onClick: onBack, children: [
      /* @__PURE__ */ jsx(ChevronLeft, { className: "mr-2 h-4 w-4" }),
      "Back"
    ] }),
    currentStep === 1 && /* @__PURE__ */ jsx(UserAccountDropdown, { variant: "standalone" }),
    currentStep < totalSteps ? /* @__PURE__ */ jsxs(Button, { onClick: onNext, disabled: !isStepValid, className: "ml-auto", children: [
      "Continue",
      /* @__PURE__ */ jsx(ChevronRight, { className: "ml-2 h-4 w-4" })
    ] }) : /* @__PURE__ */ jsx(Button, { onClick: onComplete, disabled: !isStepValid || isCreating, className: "ml-auto", children: isCreating ? /* @__PURE__ */ jsxs(Fragment, { children: [
      !authEnabled ? "Creating Organization" : "Complete Setup",
      /* @__PURE__ */ jsx(LoaderCircle, { className: "ml-2 h-4 w-4 animate-spin" })
    ] }) : /* @__PURE__ */ jsxs(Fragment, { children: [
      !authEnabled ? "Create Organization" : "Complete Setup",
      /* @__PURE__ */ jsx(Check, { className: "ml-2 h-4 w-4" })
    ] }) })
  ] });
}
export {
  OnboardingPage as component
};
