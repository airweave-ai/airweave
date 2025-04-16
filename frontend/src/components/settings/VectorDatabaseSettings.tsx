import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Database } from "lucide-react";

export function VectorDatabaseSettings() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Database className="h-5 w-5 text-primary" />
          <CardTitle>Vector Database Configuration</CardTitle>
        </div>
        <CardDescription>
          Configure your vector database settings and optimization parameters
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-2">
          <Label>Vector Dimension Size</Label>
          <Select defaultValue="1536">
            <SelectTrigger>
              <SelectValue placeholder="Select dimension size" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="768">768 (MiniBERT)</SelectItem>
              <SelectItem value="1536">1536 (OpenAI Ada)</SelectItem>
              <SelectItem value="3072">3072 (Custom)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Similarity Metric</Label>
          <RadioGroup defaultValue="cosine" className="flex gap-4">
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="cosine" id="cosine" />
              <Label htmlFor="cosine">Cosine</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="euclidean" id="euclidean" />
              <Label htmlFor="euclidean">Euclidean</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="dot" id="dot" />
              <Label htmlFor="dot">Dot Product</Label>
            </div>
          </RadioGroup>
        </div>

        <div className="space-y-2">
          <Label>Index Type</Label>
          <Select defaultValue="hnsw">
            <SelectTrigger>
              <SelectValue placeholder="Select index type" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hnsw">HNSW</SelectItem>
              <SelectItem value="flat">Flat</SelectItem>
              <SelectItem value="ivf">IVF</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}
