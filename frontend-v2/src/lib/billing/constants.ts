import {
  Database,
  Headphones,
  MessageCircle,
  Puzzle,
  Server,
  Settings,
  Shield,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";

export type PlanKey = "developer" | "pro" | "team" | "enterprise";

export interface PlanFeature {
  icon: typeof Database;
  label: string;
}

export interface PlanConfig {
  name: string;
  price: number | string;
  description: string;
  features: PlanFeature[];
}

export const plans: Record<PlanKey, PlanConfig> = {
  developer: {
    name: "Developer",
    price: "Free",
    description: "Perfect for personal agents and side projects.",
    features: [
      { icon: Database, label: "10 source connections" },
      { icon: Zap, label: "500 queries / month" },
      { icon: Zap, label: "50K entities synced / month" },
      { icon: Users, label: "1 team member" },
      { icon: MessageCircle, label: "Community support" },
    ],
  },
  pro: {
    name: "Pro",
    price: 20,
    description: "Take your agent to the next level.",
    features: [
      { icon: Database, label: "50 source connections" },
      { icon: Zap, label: "2K queries / month" },
      { icon: Zap, label: "100K entities synced / month" },
      { icon: Users, label: "2 team members" },
      { icon: MessageCircle, label: "Email support" },
    ],
  },
  team: {
    name: "Team",
    price: 299,
    description: "For fast-moving teams that need scale and control.",
    features: [
      { icon: Database, label: "1000 source connections" },
      { icon: Zap, label: "10K queries / month" },
      { icon: Zap, label: "1M entities synced / month" },
      { icon: Users, label: "10 team members" },
      { icon: MessageCircle, label: "Dedicated Slack support" },
      { icon: MessageCircle, label: "Dedicated onboarding" },
    ],
  },
  enterprise: {
    name: "Enterprise",
    price: "Custom Pricing",
    description: "Tailored solutions for large organizations.",
    features: [
      { icon: Database, label: "Unlimited source connections" },
      { icon: Settings, label: "Custom usage limits" },
      { icon: UserCheck, label: "Tailored onboarding" },
      { icon: Headphones, label: "Dedicated priority support" },
      { icon: Puzzle, label: "Custom integrations (Optional)" },
      { icon: Server, label: "On-premise deployment (Optional)" },
      { icon: Shield, label: "SLAs (Optional)" },
    ],
  },
};

export const planRank: Record<string, number> = {
  developer: 0,
  pro: 1,
  team: 2,
  enterprise: 3,
};

export function getPlanDisplayName(plan: string): string {
  return (
    plans[plan as PlanKey]?.name || plan.charAt(0).toUpperCase() + plan.slice(1)
  );
}
