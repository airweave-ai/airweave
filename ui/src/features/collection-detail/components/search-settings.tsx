import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import {
  IconBrain,
  IconFilter,
  IconFilterOff,
  IconMenu2,
  IconSortDescending,
  IconSparkles,
  IconTextSize,
  IconZoomOut,
  IconZoomPan,
} from '@tabler/icons-react'

export function SearchSettings() {
  return (
    <div className="bg-muted/20 p-4 border-l border-muted gap-4 flex flex-col">
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Search Method</Label>
        <Tabs>
          <TabsList className="mt-0 w-full">
            <TabsTrigger value="hybrid">
              <IconSparkles />
              <span>Hybrid</span>
            </TabsTrigger>
            <TabsTrigger value="neural">
              <IconBrain />
              <span>Neural</span>
            </TabsTrigger>
            <TabsTrigger value="keyword">
              <IconTextSize />
              <span>Keyword</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Query Expansion</Label>
        <Tabs>
          <TabsList className="mt-0 w-full">
            <TabsTrigger value="hybrid">
              <IconZoomPan />
              <span>On</span>
            </TabsTrigger>
            <TabsTrigger value="neural">
              <IconZoomOut />
              <span>Off</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">Query Interpretation</Label>
        <Tabs>
          <TabsList className="mt-0 w-full">
            <TabsTrigger value="hybrid">
              <IconFilter />
              <span>On</span>
            </TabsTrigger>
            <TabsTrigger value="neural">
              <IconFilterOff />
              <span>Off</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label className="text-xs">AI Reranking</Label>
        <Tabs>
          <TabsList className="mt-0 w-full">
            <TabsTrigger value="hybrid">
              <IconSortDescending />
              <span>On</span>
            </TabsTrigger>
            <TabsTrigger value="neural">
              <IconMenu2 />
              <span>Off</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-xs justify-between">
          <Label className="text-xs">Recency Bias</Label>
          <div className="font-mono">0.2</div>
        </div>
        <div className="flex items-center gap-2.5 text-xs w-66 bg-muted py-2 px-3 text-muted-foreground font-mono rounded-lg">
          <div>0</div>
          <Slider />
          <div>1</div>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2 text-xs justify-between">
          <Label className="text-xs">Metadata Filtering</Label>
        </div>
        <Textarea className="bg-card font-mono" placeholder="{}" />
      </div>
    </div>
  )
}
