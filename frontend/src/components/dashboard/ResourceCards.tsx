import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Code, Github, BarChart } from "lucide-react";
import { DiscordIcon } from "@/components/ui/discord-icon";
import { cn } from "@/lib/utils";

interface ResourceCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  icon: React.ReactNode;
  href: string;
}

const ResourceCard = React.forwardRef<HTMLDivElement, ResourceCardProps>(
  ({ title, icon, href, className, ...props }, ref) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="block h-full"
    >
      <Card
        ref={ref}
        className={cn(
          "flex flex-col items-center justify-center h-full p-6 transition-all duration-200 border hover:border-primary hover:shadow-sm",
          className
        )}
        {...props}
      >
        <div className="flex flex-col items-center text-center space-y-3">
          <div className="p-3 rounded-full bg-primary/10 text-primary">
            {icon}
          </div>
          <div className="text-lg font-medium">{title}</div>
        </div>
      </Card>
    </a>
  )
);
ResourceCard.displayName = "ResourceCard";

interface ResourceCardsProps extends React.HTMLAttributes<HTMLDivElement> {}

const ResourceCards = React.forwardRef<HTMLDivElement, ResourceCardsProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4", className)}
      {...props}
    >
      <ResourceCard
        title="API Reference"
        icon={<Code className="w-6 h-6" />}
        href="https://docs.airweave.ai/api-reference"
      />
      <ResourceCard
        title="Discord Community"
        icon={<DiscordIcon className="w-6 h-6" />}
        href="https://discord.gg/484HY9Ehxt"
      />
      <ResourceCard
        title="Blog"
        icon={<BarChart className="w-6 h-6" />}
        href="https://airweave.ai"
      />
      <ResourceCard
        title="GitHub"
        icon={<Github className="w-6 h-6" />}
        href="https://github.com/airweave-ai/airweave"
      />
    </div>
  )
);
ResourceCards.displayName = "ResourceCards";

export { ResourceCards, ResourceCard };
