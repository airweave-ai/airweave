import React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogOverlay,
} from "@/components/ui/dialog";

interface ImageModalProps {
  isOpen: boolean;
  image: string | null;
  onClose: () => void;
}

export const ImageModal = ({ isOpen, image, onClose }: ImageModalProps) => {
  if (!image) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogOverlay className="bg-background/80 backdrop-blur-sm" />
      <DialogContent className="max-w-[90vw] max-h-[90vh] p-0 border-none bg-transparent">
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 h-8 w-8 bg-background/50 hover:bg-background/80"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </Button>
          <img
            src={image}
            alt="Full size preview"
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
          />
        </div>
      </DialogContent>
    </Dialog>
  );
};
