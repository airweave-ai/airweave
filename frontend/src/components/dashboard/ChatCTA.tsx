import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MessageSquare } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useState } from "react";
import { dataSources } from "@/config/dataSources";
import { useTheme } from "@/lib/theme-provider";

export function ChatCTA() {
  const navigate = useNavigate();
  const [input, setInput] = useState("");
  const { resolvedTheme } = useTheme();
  const isDarkMode = resolvedTheme === "dark";

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      // Get the first available data source
      const defaultSource = dataSources[0]?.short_name;
      navigate("/chat", {
        state: {
          initialMessage: input.trim(),
          selectedSources: defaultSource ? [defaultSource] : []
        }
      });
    }
  };

  return (
    <Card className={`${
      isDarkMode
        ? "bg-gradient-to-r from-primary-950/30 via-primary-900/20 to-background/80"
        : "bg-gradient-to-r from-primary/5 via-primary/10 to-background"
    } backdrop-blur-sm`}>
      <CardContent className="p-6">
        <div className="mb-6">
          <h3 className="text-2xl font-bold">Chat with Your Data</h3>
          <p className="text-muted-foreground">
            Ask questions and get insights from your synchronized data
          </p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col md:flex-row items-center gap-4">
          <div className="relative flex-1 w-full">
            <Input
              placeholder="Ask a question about your data..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className={`w-full pl-10 ${
                isDarkMode
                  ? "bg-background/80 border-primary-700/30 text-foreground placeholder:text-gray-200"
                  : "bg-white/50 border-primary/20 placeholder:text-muted-foreground/70"
              } focus-visible:ring-primary/30`}
            />
            <MessageSquare className={`absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 ${
              isDarkMode ? "text-white" : "text-primary/40"
            }`} />
          </div>
          <Button type="submit" size="lg" className="whitespace-nowrap">
            Start Chatting
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
