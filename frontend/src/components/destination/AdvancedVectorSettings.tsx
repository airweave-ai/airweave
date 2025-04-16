import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Database, Cpu, Gauge } from "lucide-react";

export function AdvancedVectorSettings() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            <CardTitle>Vector Database Configuration</CardTitle>
          </div>
          <CardDescription>
            Configure advanced vector database settings
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
                <SelectItem value="1024">1024 (Custom)</SelectItem>
                <SelectItem value="1536">1536 (OpenAI Ada)</SelectItem>
                <SelectItem value="3072">3072 (Custom)</SelectItem>
                <SelectItem value="4096">4096 (Claude)</SelectItem>
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
                <SelectItem value="hnsw">HNSW (Hierarchical NSW)</SelectItem>
                <SelectItem value="flat">Flat (Exact Search)</SelectItem>
                <SelectItem value="ivf">IVF (Inverted File)</SelectItem>
                <SelectItem value="pq">PQ (Product Quantization)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>HNSW Parameters (if applicable)</Label>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label className="text-sm">M (Max Connections)</Label>
                <Input type="number" defaultValue={16} />
              </div>
              <div>
                <Label className="text-sm">ef_construction</Label>
                <Input type="number" defaultValue={100} />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Dynamic Index Building</Label>
              <p className="text-sm text-muted-foreground">
                Automatically rebuild index on updates
              </p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cpu className="h-5 w-5 text-primary" />
            <CardTitle>Entitying Configuration</CardTitle>
          </div>
          <CardDescription>
            Configure document processing and entitying
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <Label>Entity Size (tokens)</Label>
            <Slider
              defaultValue={[512]}
              max={2048}
              min={128}
              step={128}
              className="w-full"
            />
            <div className="text-sm text-muted-foreground">
              Recommended: 512 tokens for optimal context window usage
            </div>
          </div>

          <div className="space-y-2">
            <Label>Entity Overlap (%)</Label>
            <Slider
              defaultValue={[50]}
              max={100}
              min={0}
              className="w-full"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Smart Entitying</Label>
              <p className="text-sm text-muted-foreground">
                Use ML to detect natural break points
              </p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="space-y-2">
            <Label>Entitying Strategy</Label>
            <Select defaultValue="semantic">
              <SelectTrigger>
                <SelectValue placeholder="Select entitying strategy" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="semantic">Semantic (ML-based)</SelectItem>
                <SelectItem value="fixed">Fixed Size</SelectItem>
                <SelectItem value="sentence">Sentence-based</SelectItem>
                <SelectItem value="paragraph">Paragraph-based</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Preserve Metadata</Label>
              <p className="text-sm text-muted-foreground">
                Keep original document structure info
              </p>
            </div>
            <Switch defaultChecked />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-primary" />
            <CardTitle>Performance Optimization</CardTitle>
          </div>
          <CardDescription>
            Fine-tune vector search performance
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-2">
            <Label>Search Limit</Label>
            <Input type="number" defaultValue={100} />
            <p className="text-sm text-muted-foreground">
              Maximum number of vectors to return per search
            </p>
          </div>

          <div className="space-y-2">
            <Label>Batch Size</Label>
            <Select defaultValue="1000">
              <SelectTrigger>
                <SelectValue placeholder="Select batch size" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="100">100 vectors</SelectItem>
                <SelectItem value="500">500 vectors</SelectItem>
                <SelectItem value="1000">1,000 vectors</SelectItem>
                <SelectItem value="5000">5,000 vectors</SelectItem>
                <SelectItem value="10000">10,000 vectors</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              Number of vectors to process in each batch
            </p>
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Cache Results</Label>
              <p className="text-sm text-muted-foreground">
                Enable vector search caching
              </p>
            </div>
            <Switch defaultChecked />
          </div>

          <div className="space-y-2">
            <Label>Cache TTL (minutes)</Label>
            <Input type="number" defaultValue={60} />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
