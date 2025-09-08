import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { Plus, FileText, Database, Code, Maximize2, Copy, CheckCircle, ChevronRight, X } from 'lucide-react';
import { EntityState } from '@/stores/entityStateStore';
import { apiClient } from '@/lib/api';
import { DESIGN_SYSTEM } from '@/lib/design-system';

// Entity Definition type matching backend schema
interface EntityDefinition {
  id: string;
  name: string;
  description?: string;
  type: 'json' | 'file' | 'database';
  entity_schema: string[] | Record<string, any>;
  module_name: string;
  class_name: string;
  parent_id?: string;
  organization_id?: string;
}

interface EntityStateListProps {
  state: EntityState | undefined;
  sourceShortName: string;
  isDark: boolean;
  onStartSync: () => void;
  isRunning: boolean;
  isPending: boolean;
}

// Component for animated count display with blue chip effect
const AnimatedCount: React.FC<{
  count: number;
  isDark: boolean;
  className?: string;
}> = ({ count, isDark, className }) => {
  const [prevCount, setPrevCount] = useState(count);
  const [glowIntensity, setGlowIntensity] = useState(0); // 0 to 1
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (count !== prevCount && count > prevCount) {
      // Clear any existing interval
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      // Set to full intensity immediately
      setGlowIntensity(1);
      setPrevCount(count);

      // Start decay after 200ms hold
      // Clear any existing timeout before setting a new one
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      timeoutRef.current = setTimeout(() => {
        // Use setInterval for continuous decay
        intervalRef.current = setInterval(() => {
          setGlowIntensity(prev => {
            const newIntensity = prev * 0.93; // Decay rate

            // Stop when intensity is very low
            if (newIntensity < 0.01) {
              if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
              }
              return 0;
            }

            return newIntensity;
          });
        }, 50); // Update every 50ms
      }, 200); // Hold for 200ms before starting decay

    } else if (count !== prevCount) {
      setPrevCount(count);
    }

    // Cleanup on unmount or when count changes
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [count]);

  return (
    <span className="relative inline-flex items-center">
      {/* Blue chip background with dynamic opacity based on glowIntensity */}
      <span
        className={cn(
          "absolute inset-0 rounded-full transition-transform duration-200",
          glowIntensity > 0 ? "scale-110" : "scale-100"
        )}
        style={{
          padding: '2px 8px',
          margin: '0 -8px',
          backgroundColor: isDark
            ? `rgba(59, 130, 246, ${glowIntensity * 0.2})` // blue-500 with dynamic opacity
            : `rgba(96, 165, 250, ${glowIntensity * 0.2})`, // blue-400 with dynamic opacity
          transition: 'background-color 50ms ease-out'
        }}
      />

      {/* The actual count with dynamic text color */}
      <span
        className={cn(
          "relative tabular-nums",
          glowIntensity === 0 && "text-current", // Use default text color when not glowing
          className
        )}
        style={{
          color: glowIntensity > 0
            ? isDark
              ? `rgb(${Math.round(229 - (229 - 96) * glowIntensity)} ${Math.round(231 - (231 - 165) * glowIntensity)} ${Math.round(235 - (235 - 250) * glowIntensity)})` // Interpolate from gray-200 to blue-400
              : `rgb(${Math.round(31 + (37 - 31) * glowIntensity)} ${Math.round(41 + (99 - 41) * glowIntensity)} ${Math.round(55 + (235 - 55) * glowIntensity)})` // Interpolate from gray-800 to blue-600
            : undefined,
          transition: 'none' // Remove transition for smooth real-time updates
        }}
      >
        {count.toLocaleString()}
      </span>
    </span>
  );
};

// Entity Grid Item Component - Smaller and more elegant with subtle interaction hints
const EntityGridItem: React.FC<{
  entity: { name: string; count: number; definition?: EntityDefinition };
  isDark: boolean;
  isExpanded: boolean;
  onClick: () => void;
}> = ({ entity, isDark, isExpanded, onClick }) => {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative w-full min-w-[120px] rounded-md px-3 py-2 transition-all duration-300",
        "text-left focus:outline-none",
        // Disabled state for empty entities
        entity.count === 0
          ? cn(
            "cursor-not-allowed opacity-50",
            isDark ? "bg-gray-800/5 border-gray-700/5" : "bg-gray-50/30 border-gray-200/10"
          )
          : cn(
            "cursor-pointer hover:shadow-sm active:scale-[0.995]",
            isExpanded
              ? isDark
                ? "bg-blue-500/10 border-blue-500/30 shadow-sm"
                : "bg-blue-50 border-blue-200/60 shadow-sm"
              : isDark
                ? "bg-gray-800/10 hover:bg-gray-800/30 border-gray-700/20 hover:border-gray-600/40"
                : "bg-white/70 hover:bg-white border-gray-200/40 hover:border-gray-300/60"
          ),
        "border"
      )}
      disabled={entity.count === 0}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span
            className={cn(
              "text-[11px] font-medium truncate transition-colors duration-300 block",
              isExpanded
                ? isDark ? "text-blue-400" : "text-blue-600"
                : isDark ? "text-gray-300" : "text-gray-700"
            )}
            title={entity.name}
          >
            {entity.name}
          </span>
          {/* Always visible indicator for expandable items */}
          {entity.count > 0 && (
            <div className="flex items-center gap-1">
              <ChevronRight className={cn(
                "h-3 w-3 flex-shrink-0 transition-all duration-300",
                isExpanded
                  ? "rotate-90"
                  : cn(
                    "opacity-25 group-hover:opacity-60",
                    isDark ? "text-gray-400" : "text-gray-600"
                  )
              )} />
              {/* Show "view" text on hover */}
              {!isExpanded && (
                <span className={cn(
                  "text-[9px] font-normal transition-all duration-300 overflow-hidden",
                  "opacity-0 group-hover:opacity-50 max-w-0 group-hover:max-w-[30px]",
                  isDark ? "text-gray-400" : "text-gray-500"
                )}>
                  view
                </span>
              )}
            </div>
          )}
        </div>
        <AnimatedCount
          count={entity.count}
          isDark={isDark}
          className={cn(
            "text-xs font-semibold tabular-nums flex-shrink-0",
            entity.count === 0 && "opacity-30"
          )}
        />
      </div>


    </button>
  );
};

// Component for displaying simplified schema
const SimplifiedSchemaView: React.FC<{ schema: any; isDark: boolean }> = ({ schema, isDark }) => {
  if (!schema || !schema.properties) {
    return (
      <pre className="text-xs font-mono text-muted-foreground p-4">
        {JSON.stringify(schema, null, 2)}
      </pre>
    );
  }

  const properties = Object.entries(schema.properties).filter(([key]) => key !== '...');
  const required = schema.required || [];

  // Separate required and optional fields
  const requiredFields = properties.filter(([key]) => required.includes(key));
  const optionalFields = properties.filter(([key]) => !required.includes(key));

  return (
    <div className="py-1">
      {/* Required fields section */}
      {requiredFields.length > 0 && (
        <div className="relative mb-2">
          <span className="absolute -top-1 right-4 text-[10px] font-normal tracking-wider text-muted-foreground/40">
            MANDATORY
          </span>
          <div className="space-y-0 pt-1">
            {requiredFields.map(([key, value]) => {
              const typeInfo = typeof value === 'object' && value && 'type' in value ? value as any : { type: value };
              const typeStr = typeof typeInfo.type === 'string' ? typeInfo.type : 'object';
              const description = typeInfo.description;

              return (
                <div key={key} className="group py-0.5 px-4">
                  <div className="flex items-baseline gap-3">
                    <div className="flex items-center gap-1.5 min-w-[140px]">
                      <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "font-mono font-medium")}>
                        {key}
                      </span>
                      <span className="text-red-500 text-[10px]">•</span>
                    </div>
                    <span className={cn(
                      DESIGN_SYSTEM.typography.sizes.label,
                      "font-mono px-1.5 py-0.5 rounded",
                      isDark ? "text-blue-400 bg-blue-400/10" : "text-blue-700 bg-blue-50"
                    )}>
                      {typeStr}
                    </span>
                    {description && (
                      <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "text-muted-foreground flex-1")}>
                        {description}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Divider */}
      {requiredFields.length > 0 && optionalFields.length > 0 && (
        <div className="h-px bg-border/30 mx-2 my-2" />
      )}

      {/* Optional fields section */}
      {optionalFields.length > 0 && (
        <div className="relative">
          <span className="absolute -top-1 right-4 text-[10px] font-normal tracking-wider text-muted-foreground/40">
            OPTIONAL
          </span>
          <div className="space-y-0 pt-1">
            {optionalFields.map(([key, value]) => {
              const typeInfo = typeof value === 'object' && value && 'type' in value ? value as any : { type: value };
              const typeStr = typeof typeInfo.type === 'string' ? typeInfo.type : 'object';
              const description = typeInfo.description;

              return (
                <div key={key} className="group py-0.5 px-4">
                  <div className="flex items-baseline gap-3">
                    <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "font-mono min-w-[140px]")}>
                      {key}
                    </span>
                    <span className={cn(
                      DESIGN_SYSTEM.typography.sizes.label,
                      "font-mono px-1.5 py-0.5 rounded",
                      isDark ? "text-gray-400 bg-gray-400/10" : "text-gray-600 bg-gray-100"
                    )}>
                      {typeStr}
                    </span>
                    {description && (
                      <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "text-muted-foreground flex-1")}>
                        {description}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

// Detailed Entity View Component - Separated card design
const EntityDetailView: React.FC<{
  entity: { name: string; count: number; definition?: EntityDefinition };
  isDark: boolean;
  onClose: () => void;
}> = ({ entity, isDark, onClose }) => {
  const [copiedSchema, setCopiedSchema] = useState(false);

  const copySchema = () => {
    if (entity.definition?.entity_schema) {
      const schemaText = JSON.stringify(entity.definition.entity_schema, null, 2);
      navigator.clipboard.writeText(schemaText);
      setCopiedSchema(true);
      setTimeout(() => setCopiedSchema(false), 2000);
    }
  };

  return (
    <Card className={cn(
      "overflow-hidden flex flex-col max-h-[500px]",
      isDark ? "bg-gray-900/40 border-gray-800" : "bg-white border-gray-200"
    )}>
      <Tabs defaultValue="schema" className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* Compact Header */}
        <div className={cn(
          "border-b px-4 py-2.5 flex-shrink-0",
          isDark ? "border-gray-800" : "border-gray-200"
        )}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h4 className="text-sm font-medium">
                {entity.name}
              </h4>
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                {entity.count.toLocaleString()} synced
              </Badge>
            </div>

            <div className="flex items-center gap-2">
              {/* Tab Buttons */}
              <TabsList className={cn(
                "h-7 p-0.5 rounded-md",
                isDark ? "bg-gray-800/60" : "bg-gray-100"
              )}>
                <TabsTrigger
                  value="schema"
                  className={cn(
                    "h-6 px-2.5 text-[11px] font-medium rounded",
                    "data-[state=active]:bg-background data-[state=active]:shadow-sm",
                    "transition-all duration-150"
                  )}
                >
                  Schema
                </TabsTrigger>
                <TabsTrigger
                  value="example"
                  className={cn(
                    "h-6 px-2.5 text-[11px] font-medium rounded",
                    "data-[state=active]:bg-background data-[state=active]:shadow-sm",
                    "transition-all duration-150"
                  )}
                >
                  Example
                </TabsTrigger>
              </TabsList>

              {/* Close button */}
              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  DESIGN_SYSTEM.buttons.heights.compact,
                  "w-6",
                  DESIGN_SYSTEM.radius.button
                )}
                onClick={onClose}
              >
                <X className={DESIGN_SYSTEM.icons.inline} />
              </Button>
            </div>
          </div>
          {entity.definition?.description && (
            <p className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground mt-1")}>
              {entity.definition.description}
            </p>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-hidden">
          <TabsContent value="schema" className="h-full max-h-[400px] overflow-y-auto overflow-x-hidden scrollbar-thin">
            {entity.definition ? (
              <div className={cn("space-y-3 pb-2 px-1", DESIGN_SYSTEM.typography.sizes.body)}>
                {/* Schema Display */}
                <div className="relative group">
                  <Button
                    variant="ghost"
                    size="icon"
                    className={cn(
                      "absolute -top-1 right-0 w-6 opacity-0 group-hover:opacity-100 transition-opacity z-10",
                      DESIGN_SYSTEM.buttons.heights.compact,
                      isDark ? "hover:bg-gray-800" : "hover:bg-white/80"
                    )}
                    onClick={copySchema}
                  >
                    {copiedSchema ? (
                      <CheckCircle className={cn(DESIGN_SYSTEM.icons.inline, "text-green-500")} />
                    ) : (
                      <Copy className={DESIGN_SYSTEM.icons.inline} />
                    )}
                  </Button>

                  <div className="overflow-x-auto">
                    {(() => {
                      try {
                        const schema = entity.definition.entity_schema;

                        // Handle file type entities
                        if (entity.definition.type === 'file' && Array.isArray(schema)) {
                          return (
                            <div className={cn(DESIGN_SYSTEM.typography.sizes.body)}>
                              <span className="text-muted-foreground">Supported: </span>
                              <span className="font-mono">
                                {(schema as string[]).join(', ')}
                              </span>
                            </div>
                          );
                        }

                        // Parse string schemas
                        const parsedSchema = typeof schema === 'string'
                          ? JSON.parse(schema)
                          : schema;

                        return (
                          <SimplifiedSchemaView
                            schema={parsedSchema}
                            isDark={isDark}
                          />
                        );
                      } catch (error) {
                        console.error('Error parsing schema:', error);
                        return (
                          <div className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground")}>
                            Error loading schema
                          </div>
                        );
                      }
                    })()}
                  </div>
                </div>

                {/* Technical Details - More Compact */}
                <div className="space-y-1.5 pt-1 border-t border-border/30 px-4">
                  <h5 className={cn(
                    DESIGN_SYSTEM.typography.sizes.label,
                    DESIGN_SYSTEM.typography.weights.medium,
                    DESIGN_SYSTEM.typography.cases.uppercase,
                    DESIGN_SYSTEM.typography.tracking.wider,
                    "text-muted-foreground"
                  )}>
                    Technical Details
                  </h5>
                  <div className="space-y-0.5">
                    <div className={cn("flex items-center justify-between", DESIGN_SYSTEM.typography.sizes.body)}>
                      <span className="text-muted-foreground">Module</span>
                      <code className={cn(DESIGN_SYSTEM.typography.sizes.label, "font-mono")}>
                        {entity.definition.module_name}
                      </code>
                    </div>
                    <div className={cn("flex items-center justify-between", DESIGN_SYSTEM.typography.sizes.body)}>
                      <span className="text-muted-foreground">Class</span>
                      <code className={cn(DESIGN_SYSTEM.typography.sizes.label, "font-mono")}>
                        {entity.definition.class_name}
                      </code>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground p-4")}>
                No schema available
              </div>
            )}
          </TabsContent>

          <TabsContent value="example" className="h-full max-h-[400px] overflow-y-auto overflow-x-hidden scrollbar-thin px-4 py-3">
            <div className={cn(
              "rounded-lg border p-8 mt-4",
              isDark
                ? "bg-gray-900/20 border-gray-800/50"
                : "bg-gray-50/50 border-gray-200/50"
            )}>
              <div className="text-center space-y-3">
                <div className={cn(
                  "inline-flex p-2.5 rounded-full",
                  isDark ? "bg-gray-800/50" : "bg-gray-100"
                )}>
                  <FileText className="h-5 w-5 text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm font-medium mb-1">Coming Soon</p>
                  <p className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground")}>
                    Example data preview will be available in a future update
                  </p>
                </div>
              </div>
            </div>
          </TabsContent>
        </div>
      </Tabs>
    </Card>
  );
};

// Custom hook for smooth height transitions
const useHeightTransition = (isOpen: boolean) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState<number>(0);
  const [shouldRender, setShouldRender] = useState(false);
  const measureTimeoutRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    if (isOpen) {
      setShouldRender(true);
      // Measure height after render
      measureTimeoutRef.current = setTimeout(() => {
        if (containerRef.current) {
          const contentElement = containerRef.current.firstElementChild as HTMLElement;
          if (contentElement) {
            const newHeight = contentElement.scrollHeight;
            setHeight(newHeight);
          }
        }
      }, 10);
    } else {
      setHeight(0);
      // Delay unmounting to allow close animation
      const timer = setTimeout(() => setShouldRender(false), 300);
      return () => clearTimeout(timer);
    }

    return () => {
      if (measureTimeoutRef.current) {
        clearTimeout(measureTimeoutRef.current);
      }
    };
  }, [isOpen]);

  // Re-measure on content changes
  useEffect(() => {
    if (isOpen && shouldRender && containerRef.current) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const newHeight = entry.contentRect.height;
          if (newHeight > 0) {
            setHeight(newHeight);
          }
        }
      });

      const contentElement = containerRef.current.firstElementChild as HTMLElement;
      if (contentElement) {
        resizeObserver.observe(contentElement);
      }

      return () => resizeObserver.disconnect();
    }
  }, [isOpen, shouldRender]);

  return { containerRef, height, shouldRender };
};

export const EntityStateList: React.FC<EntityStateListProps> = ({
  state,
  sourceShortName,
  isDark,
  onStartSync,
  isRunning,
  isPending
}) => {
  const [expandedEntity, setExpandedEntity] = useState<string | null>(null);
  const [entityDefinitions, setEntityDefinitions] = useState<EntityDefinition[]>([]);
  const [isLoadingDefinitions, setIsLoadingDefinitions] = useState(true);
  const isSyncing = isRunning || isPending;

  // Fetch entity definitions for this source
  useEffect(() => {
    const fetchEntityDefinitions = async () => {
      if (!sourceShortName) return;

      try {
        setIsLoadingDefinitions(true);
        const response = await apiClient.get(`/entities/definitions/by-source/?source_short_name=${sourceShortName}`);
        if (response.ok) {
          const data = await response.json();
          setEntityDefinitions(data);
        } else {
          console.error('Failed to fetch entity definitions:', response.status);
        }
      } catch (error) {
        console.error('Failed to fetch entity definitions:', error);
      } finally {
        setIsLoadingDefinitions(false);
      }
    };

    fetchEntityDefinitions();
  }, [sourceShortName]);

  // Combine state counts with entity definitions
  const combinedEntities = React.useMemo(() => {
    const entityMap = new Map<string, { name: string; count: number; definition?: EntityDefinition }>();

    // Create a mapping from simplified names to definitions
    // E.g., "AsanaTaskEntity" -> "AsanaTask"
    const defBySimpleName = new Map<string, EntityDefinition>();
    entityDefinitions.forEach(def => {
      if (!def.name.includes('Chunk') && !def.name.includes('Parent')) {
        // Remove "Entity" suffix if present for matching
        const simpleName = def.name.replace(/Entity$/, '');
        defBySimpleName.set(simpleName, def);
      }
    });

    // Build combined list from entity counts (which use simple names)
    if (state?.entityCounts) {
      Object.entries(state.entityCounts).forEach(([name, count]) => {
        if (!name.includes('Chunk') && !name.includes('Parent')) {
          const definition = defBySimpleName.get(name);
          entityMap.set(name, {
            name,
            count: count as number,
            definition
          });
        }
      });
    }

    // Add any definitions that don't have counts yet
    defBySimpleName.forEach((def, simpleName) => {
      if (!entityMap.has(simpleName)) {
        entityMap.set(simpleName, {
          name: simpleName,
          count: 0,
          definition: def
        });
      }
    });

    // Sort by count (descending) then by name
    return Array.from(entityMap.values()).sort((a, b) => {
      if (b.count !== a.count) return b.count - a.count;
      return a.name.localeCompare(b.name);
    });
  }, [state?.entityCounts, entityDefinitions]);

  // Calculate total
  const totalCount = React.useMemo(() => {
    return combinedEntities.reduce((sum, entity) => sum + entity.count, 0);
  }, [combinedEntities]);

  const handleEntityClick = (entityName: string) => {
    console.log('EntityClick:', entityName, 'Current expanded:', expandedEntity);

    if (expandedEntity === entityName) {
      // Closing the same entity
      setExpandedEntity(null);
    } else {
      // Check if entity exists before expanding
      const entity = combinedEntities.find(e => e.name === entityName);
      console.log('Found entity:', entity);

      if (entity) {
        // Opening a new entity or switching - direct transition
        setExpandedEntity(entityName);

        // Smooth scroll to show the expanded content after a brief delay
        setTimeout(() => {
          const element = document.getElementById('entity-detail-view');
          if (element) {
            element.scrollIntoView({
              behavior: 'smooth',
              block: 'nearest',
              inline: 'nearest'
            });
          }
        }, 100);
      }
    }
  };

  // Use height transition for detail view
  const expandedEntityData = expandedEntity ? combinedEntities.find(e => e.name === expandedEntity) : null;

  console.log('Expanded state:', { expandedEntity, expandedEntityData, combinedEntitiesCount: combinedEntities.length });

  // If expandedEntity is set but data not found, clear it
  useEffect(() => {
    if (expandedEntity && !combinedEntities.find(e => e.name === expandedEntity)) {
      console.log('Clearing orphaned expanded entity:', expandedEntity);
      setExpandedEntity(null);
    }
  }, [expandedEntity, combinedEntities]);

  const { containerRef, height, shouldRender } = useHeightTransition(!!expandedEntityData);

  return (
    <div className={cn("space-y-3", DESIGN_SYSTEM.typography.sizes.body)}>
      {/* Main Entities Card */}
      <Card className={cn(
        "overflow-hidden relative transition-all duration-500",
        DESIGN_SYSTEM.radius.card,
        isDark ? "bg-gray-900/40" : "bg-white",
        // Subtle animated border for sync status
        isSyncing ? "border-transparent" : isDark ? "border-gray-800" : "border-gray-200"
      )}
        style={{
          // Custom animated border using CSS gradient
          ...(isSyncing && {
            background: isDark
              ? `linear-gradient(${isDark ? '#1a1f2e' : '#ffffff'}, ${isDark ? '#1a1f2e' : '#ffffff'}) padding-box,
               linear-gradient(90deg,
                 ${isRunning ? '#3b82f6' : '#eab308'} 0%,
                 ${isRunning ? '#60a5fa' : '#fbbf24'} 25%,
                 ${isRunning ? '#3b82f6' : '#eab308'} 50%,
                 ${isRunning ? '#60a5fa' : '#fbbf24'} 75%,
                 ${isRunning ? '#3b82f6' : '#eab308'} 100%) border-box`
              : `linear-gradient(white, white) padding-box,
               linear-gradient(90deg,
                 ${isRunning ? '#3b82f6' : '#eab308'} 0%,
                 ${isRunning ? '#60a5fa' : '#fbbf24'} 25%,
                 ${isRunning ? '#3b82f6' : '#eab308'} 50%,
                 ${isRunning ? '#60a5fa' : '#fbbf24'} 75%,
                 ${isRunning ? '#3b82f6' : '#eab308'} 100%) border-box`,
            border: '1px solid transparent',
            backgroundSize: isSyncing ? '200% 100%, 200% 100%' : '100% 100%, 100% 100%',
            backgroundPosition: isSyncing ? '0 0, 0 0' : '0 0, 0 0',
            animation: isSyncing ? 'borderSlide 3s linear infinite' : 'none',
          })
        }}>
        <CardContent className="p-4">
          {/* Compact Header */}
          <div className={cn("flex items-center mb-4", DESIGN_SYSTEM.spacing.gaps.standard)}>
            <h3 className={cn(
              DESIGN_SYSTEM.typography.sizes.label,
              DESIGN_SYSTEM.typography.weights.semibold,
              DESIGN_SYSTEM.typography.cases.uppercase,
              DESIGN_SYSTEM.typography.tracking.wider,
              "text-muted-foreground"
            )}>
              Entities
            </h3>
            <span className={cn(DESIGN_SYSTEM.typography.sizes.label, "text-muted-foreground")}>
              • {totalCount} total
            </span>
          </div>

          {/* Content */}
          {isLoadingDefinitions ? (
            <div className="flex items-center justify-center py-12">
              <div className={cn(DESIGN_SYSTEM.typography.sizes.body, "text-muted-foreground")}>Loading entities...</div>
            </div>
          ) : combinedEntities.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className={cn(
                  "inline-flex p-3 rounded-full mb-3",
                  isDark ? "bg-gray-800/40" : "bg-gray-100"
                )}>
                  <Database className="h-5 w-5 text-muted-foreground" />
                </div>
                <h3 className={cn(
                  DESIGN_SYSTEM.typography.sizes.header,
                  DESIGN_SYSTEM.typography.weights.medium,
                  "mb-1"
                )}>No entities synced</h3>
                <p className={cn(
                  DESIGN_SYSTEM.typography.sizes.body,
                  "text-muted-foreground mb-3 max-w-[200px] mx-auto"
                )}>
                  Start a sync to see your data entities
                </p>
                <Button
                  onClick={onStartSync}
                  variant="outline"
                  size="sm"
                  className={cn(
                    DESIGN_SYSTEM.buttons.heights.compact,
                    DESIGN_SYSTEM.typography.sizes.body,
                    DESIGN_SYSTEM.buttons.padding.secondary
                  )}
                >
                  <Plus className={cn(DESIGN_SYSTEM.icons.inline, "mr-1")} />
                  Start Sync
                </Button>
              </div>
            </div>
          ) : (
            /* Compact Entity Grid - Optimized for readability */
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-1.5">
              {combinedEntities.map((entity) => (
                <EntityGridItem
                  key={entity.name}
                  entity={entity}
                  isDark={isDark}
                  isExpanded={expandedEntityData?.name === entity.name}
                  onClick={() => handleEntityClick(entity.name)}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Separated Detail View with smooth height transition */}
      <div
        id="entity-detail-view"
        ref={containerRef}
        style={{
          height: `${height}px`,
          transition: 'height 300ms cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'hidden'
        }}
      >
        {shouldRender && expandedEntityData && (
          <div className={cn(
            "transition-opacity duration-200",
            expandedEntityData ? "opacity-100" : "opacity-0"
          )}>
            <EntityDetailView
              entity={expandedEntityData}
              isDark={isDark}
              onClose={() => setExpandedEntity(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default EntityStateList;
