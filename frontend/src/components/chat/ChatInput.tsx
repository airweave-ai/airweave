import { useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Send, Image, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSubmit: (message: string, attachments: string[]) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export const ChatInput = ({ onSubmit, isLoading, disabled = false }: ChatInputProps) => {
  const [input, setInput] = useState("");
  const [pendingImages, setPendingImages] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files) return;

    const filePromises = Array.from(files).map((file) => {
      return new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          resolve(reader.result as string);
        };
        reader.readAsDataURL(file);
      });
    });

    Promise.all(filePromises).then((fileDataUrls) => {
      setPendingImages((prev) => [...prev, ...fileDataUrls]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim() || pendingImages.length > 0) {
      onSubmit(input, pendingImages);
      setInput("");
      setPendingImages([]);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2">
        <input
          type="file"
          multiple
          className="hidden"
          ref={fileInputRef}
          onChange={handleFileUpload}
          accept="image/*"
        />
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
        >
          <Image className="h-4 w-4" />
        </Button>
        <Input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your data..."
          className="flex-1"
          disabled={isLoading || disabled}
        />
        <Button type="submit" disabled={isLoading || disabled} className="bg-primary/50 text-primary-foreground hover:bg-primary/70">
          {isLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </div>
    </form>
  );
};
