import { Button } from "@/components/ui/button";
import { BookOpen } from "lucide-react";
import { useTheme } from "@/lib/theme-provider";

export function DocsCard() {
  const { resolvedTheme } = useTheme();
  const isDarkMode = resolvedTheme === "dark";

  const handleDocsClick = () => {
    window.open("https://docs.airweave.ai", "_blank");
  };

  return (
    <div className={`relative overflow-hidden rounded-lg border ${
      isDarkMode
        ? "bg-gradient-to-br from-primary-950/50 to-secondary-950/50 border-primary-800/30"
        : "bg-gradient-to-br from-primary-100 to-secondary-100"
    } p-8`}>
      {/* Book illustration background */}
      <div
        className={`absolute inset-0 ${isDarkMode ? "opacity-5" : "opacity-10"}`}
        style={{
          background: `
            radial-gradient(circle at 70% 20%, rgba(255, 255, 255, 0.8) 0%, transparent 25%),
            linear-gradient(109.6deg, rgba(223,234,247,0.6) 11.2%, rgba(244,248,252,0.6) 91.1%)
          `
        }}
      />
      <div
        className={`absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/4 w-64 h-64 ${isDarkMode ? "opacity-5" : "opacity-20"}`}
        style={{
          background: 'radial-gradient(circle at center, rgba(255,255,255,0.8) 0%, transparent 70%)',
          clipPath: 'path("M10,10 h40 a10,10 0 0 1 10,10 v60 a10,10 0 0 1 -10,10 h-40 a10,10 0 0 1 -10,-10 v-60 a10,10 0 0 1 10,-10 z")',
          transform: 'rotate(-15deg) translateX(20%)'
        }}
      />

      {/* Content */}
      <div className="relative z-10 space-y-4">
        <div className="flex items-center space-x-2">
          <BookOpen className="h-6 w-6 text-primary-500" />
          <h3 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-primary-500 to-secondary-500 bg-clip-text text-transparent">
            Documentation
          </h3>
        </div>
        <p className={`${isDarkMode ? "text-gray-300" : "text-muted-foreground"} max-w-[280px] leading-relaxed`}>
          Learn about advanced features, API integrations, and best practices for vector synchronization
        </p>
        <Button
          onClick={handleDocsClick}
          className={`${
            isDarkMode
              ? "bg-primary-800 text-white hover:bg-primary-700"
              : "bg-white text-primary-400 hover:bg-primary-100 hover:text-primary-500"
          } transition-all duration-300 shadow-sm hover:shadow-md`}
        >
          <BookOpen className="mr-2 h-4 w-4" />
          Go to Docs
        </Button>
      </div>

      {/* Decorative elements */}
      <div
        className={`absolute right-0 top-0 h-full w-1/3 animate-float ${isDarkMode ? "opacity-10" : ""}`}
        style={{
          background: isDarkMode
            ? "linear-gradient(109.6deg, rgba(13,24,37,0.3) 11.2%, rgba(14,28,42,0.3) 91.1%)"
            : "linear-gradient(109.6deg, rgba(223,234,247,0.3) 11.2%, rgba(244,248,252,0.3) 91.1%)",
          borderRadius: "50%",
          transform: "translate(25%, -25%)",
        }}
      />
      <div
        className="absolute -bottom-8 -left-8 w-32 h-32 opacity-20"
        style={{
          background: 'radial-gradient(circle at center, rgba(0,103,255,0.4) 0%, transparent 70%)',
          filter: 'blur(20px)'
        }}
      />
    </div>
  );
}
