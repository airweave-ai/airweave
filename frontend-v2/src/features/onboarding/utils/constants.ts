import {
  Cloud,
  Code2,
  Cpu,
  Database,
  Globe,
  Rocket,
  Shield,
  Sparkles,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface OrganizationSize {
  value: string;
  label: string;
  description: string;
}

export const ORGANIZATION_SIZES: OrganizationSize[] = [
  { value: "1", label: "1", description: "Solo" },
  { value: "2-5", label: "2-5", description: "Small team" },
  { value: "6-20", label: "6-20", description: "Growing startup" },
  { value: "21-100", label: "21-100", description: "Scale-up" },
  { value: "101-500", label: "101-500", description: "Mid-market" },
  { value: "500+", label: "500+", description: "Enterprise" },
];

export interface UserRole {
  value: string;
  label: string;
  icon: LucideIcon;
}

export const USER_ROLES: UserRole[] = [
  { value: "founder", label: "Founder/CEO", icon: Sparkles },
  { value: "engineering", label: "Engineering", icon: Code2 },
  { value: "data", label: "Data/AI", icon: Database },
  { value: "product", label: "Product", icon: Rocket },
  { value: "devops", label: "DevOps", icon: Cloud },
  { value: "other", label: "Other", icon: Users },
];

export interface OrganizationType {
  value: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const ORGANIZATION_TYPES: OrganizationType[] = [
  {
    value: "ai_startup",
    label: "AI/ML Startup",
    icon: Cpu,
    description: "Building AI-powered products",
  },
  {
    value: "saas",
    label: "SaaS Platform",
    icon: Cloud,
    description: "Cloud-based software services",
  },
  {
    value: "data_platform",
    label: "Data Platform",
    icon: Database,
    description: "Data infrastructure & analytics",
  },
  {
    value: "dev_tools",
    label: "Developer Tools",
    icon: Code2,
    description: "Tools for developers",
  },
  {
    value: "fintech",
    label: "Fintech",
    icon: Shield,
    description: "Financial technology",
  },
  {
    value: "other",
    label: "Other",
    icon: Globe,
    description: "Other industries",
  },
];

export interface SubscriptionPlan {
  value: string;
  label: string;
  price: string;
  yearlyPrice?: string;
  period: string;
  description: string;
  features: string[];
  teamMemberLimit: number;
  recommended: boolean;
}

export const SUBSCRIPTION_PLANS: SubscriptionPlan[] = [
  {
    value: "developer",
    label: "Developer",
    price: "Free",
    period: "",
    description:
      "Perfect for personal agents and side projects. No credit card required.",
    features: [
      "10 source connections",
      "500 queries / mo",
      "50K entities / mo",
      "1 team member",
      "Community support",
    ],
    teamMemberLimit: 1,
    recommended: false,
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
      "Email support",
    ],
    teamMemberLimit: 2,
    recommended: true,
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
      "Dedicated onboarding",
    ],
    teamMemberLimit: 10,
    recommended: false,
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
      "SLAs (Optional)",
    ],
    teamMemberLimit: 1000,
    recommended: false,
  },
];

export interface TeamMember {
  email: string;
  role: "member" | "admin";
}

export interface OnboardingData {
  organizationName: string;
  organizationSize: string;
  userRole: string;
  organizationType: string;
  subscriptionPlan: string;
  teamMembers: TeamMember[];
  billingPeriod: "monthly" | "yearly";
}

export const DEFAULT_ONBOARDING_DATA: OnboardingData = {
  organizationName: "",
  organizationSize: "",
  userRole: "",
  organizationType: "",
  subscriptionPlan: "pro",
  teamMembers: [],
  billingPeriod: "monthly",
};

