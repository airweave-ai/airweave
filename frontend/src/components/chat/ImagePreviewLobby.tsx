import React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ImageModal } from "./ImageModal";

interface ImagePreviewLobbyProps {
  images: string[];
  onRemove: (index: number) => void;
}

export const ImagePreviewLobby = ({ images, onRemove }: ImagePreviewLobbyProps) => {
  const [selectedImage, setSelectedImage] = React.useState<string | null>(null);

  if (images.length === 0) return null;

  return (
    <>
      <div className="flex flex-wrap gap-2 p-2 bg-muted/20 rounded-lg mb-2">
        {images.map((image, index) => (
          <div key={index} className="relative group">
            <img
              src={image}
              alt={`Preview ${index + 1}`}
              className="w-20 h-20 object-cover rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
              onClick={() => setSelectedImage(image)}
            />
            <Button
              variant="ghost"
              size="icon"
              className="absolute top-1 right-1 h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity bg-background/50 hover:bg-background/80"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(index);
              }}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
      <ImageModal
        isOpen={!!selectedImage}
        image={selectedImage}
        onClose={() => setSelectedImage(null)}
      />
    </>
  );
};
