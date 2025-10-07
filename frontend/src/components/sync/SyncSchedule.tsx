import React, { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ClockIcon, ZapIcon, Zap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { CronExpressionInput, isValidCronExpression } from "./CronExpressionInput";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

// Custom Number1Icon component
const Number1Icon = ({ className }: { className?: string }) => (
  <div className={cn("relative flex items-center justify-center", className)}>
    <span className="font-bold text-2xl leading-none">1</span>
  </div>
);

export interface SyncScheduleConfig {
  type: "one-time" | "scheduled";
  frequency?: "every-5-min" | "every-15-min" | "every-30-min" | "hourly" | "daily" | "weekly" | "monthly" | "custom";
  hour?: number;
  minute?: number;
  dayOfWeek?: number;
  dayOfMonth?: number;
  cronExpression?: string;
}

interface SyncScheduleProps {
  value: SyncScheduleConfig;
  onChange: (config: SyncScheduleConfig) => void;
  supportsContinuous?: boolean;  // Whether source supports minute-level continuous syncing
  sourceName?: string;  // Source name for display in informational messages
}

/**
 * Converts the UI schedule configuration to a cron expression
 */
export const buildCronExpression = (config: SyncScheduleConfig): string | null => {
  if (config.type !== "scheduled") return null;

  const { frequency, hour, minute, dayOfWeek, dayOfMonth, cronExpression } = config;

  // If using custom cron expression, use as-is
  if (frequency === "custom" && cronExpression) {
    return cronExpression;
  }

  // Handle minute-level continuous sync frequencies
  switch (frequency) {
    case "every-5-min":
      return "*/5 * * * *";  // Every 5 minutes
    case "every-15-min":
      return "*/15 * * * *"; // Every 15 minutes
    case "every-30-min":
      return "*/30 * * * *"; // Every 30 minutes
  }

  // Convert local time to UTC time for storage
  let utcMinute = minute || 0;
  let utcHour = hour || 0;

  // No need to convert if hour is not used (hourly frequency)
  if (frequency !== "hourly" && hour !== undefined) {
    // The hour value is already in UTC from the dropdown selection, no need to convert again
    utcHour = hour;
    utcMinute = minute || 0;
  }

  switch (frequency) {
    case "hourly":
      return `${utcMinute} * * * *`; // At the specified minute of every hour
    case "daily":
      return `${utcMinute} ${utcHour} * * *`; // At the specified time every day
    case "weekly":
      return `${utcMinute} ${utcHour} * * ${dayOfWeek || 1}`; // Specified time on specified day of week
    case "monthly":
      return `${utcMinute} ${utcHour} ${dayOfMonth || 1} * *`; // Specified time on specified day of month
    default:
      return "0 9 * * *"; // Default to daily at 9:00 AM UTC
  }
};

export function SyncSchedule({ value, onChange, supportsContinuous = false, sourceName }: SyncScheduleProps) {
  const [activeType, setActiveType] = useState<"one-time" | "scheduled">(value.type);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleTypeChange = (type: "one-time" | "scheduled") => {
    setActiveType(type);
    onChange({
      ...value,
      type
    });
  };

  const handleFrequencyChange = (frequency: string) => {
    // Initialize default cronExpression for custom frequency
    const newConfig = {
      ...value,
      frequency: frequency as SyncScheduleConfig["frequency"]
    };

    if (frequency === "custom" && !value.cronExpression) {
      newConfig.cronExpression = "* * * * *";
    }

    onChange(newConfig);
    setValidationError(null);
  };

  const handleTimeChange = (field: string, fieldValue: string | number) => {
    onChange({
      ...value,
      [field]: fieldValue
    });
    setValidationError(null);
  };

  // Validate cron expression if needed
  const isCronValid = () => {
    if (value.type === "scheduled" && value.frequency === "custom" && value.cronExpression) {
      return isValidCronExpression(value.cronExpression);
    }
    return true;
  };

  return (
    <div className="space-y-4">
      {/* Main sync type selection */}
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-foreground">How often should we sync?</h3>
        <div className="grid grid-cols-3 gap-1.5">
          <div
            className={cn(
              "group cursor-pointer rounded-md border p-3 transition-all duration-200 hover:shadow-sm",
              activeType === "one-time"
                ? "bg-primary/5 border-primary shadow-sm"
                : "bg-card border-border hover:border-border/80"
            )}
            onClick={() => handleTypeChange("one-time")}
          >
            <div className="flex flex-col items-center text-center space-y-1.5">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center transition-colors",
                activeType === "one-time"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground group-hover:bg-muted/80"
              )}>
                <Number1Icon className="text-xs" />
              </div>
              <div>
                <h4 className="font-medium text-xs">Run once</h4>
                <p className="text-xs text-muted-foreground">
                  Manual trigger
                </p>
              </div>
            </div>
          </div>

          <div
            className={cn(
              "group cursor-pointer rounded-md border p-3 transition-all duration-200 hover:shadow-sm",
              activeType === "scheduled"
                ? "bg-primary/5 border-primary shadow-sm"
                : "bg-card border-border hover:border-border/80"
            )}
            onClick={() => handleTypeChange("scheduled")}
          >
            <div className="flex flex-col items-center text-center space-y-1.5">
              <div className={cn(
                "w-6 h-6 rounded-full flex items-center justify-center transition-colors",
                activeType === "scheduled"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground group-hover:bg-muted/80"
              )}>
                <ClockIcon className="h-3 w-3" />
              </div>
              <div>
                <h4 className="font-medium text-xs">Recurring</h4>
                <p className="text-xs text-muted-foreground">
                  Auto-sync
                </p>
              </div>
            </div>
          </div>

          <div className="group relative rounded-md border border-dashed border-muted/50 p-3 bg-muted/20 cursor-not-allowed">
            <div className="absolute top-1 right-1">
              <div className="bg-primary/20 text-primary text-xs font-bold py-0.5 px-1 rounded-full">
                PRO
              </div>
            </div>
            <div className="flex flex-col items-center text-center space-y-1.5">
              <div className="w-6 h-6 rounded-full bg-muted/50 flex items-center justify-center">
                <ZapIcon className="h-3 w-3 text-muted-foreground" />
              </div>
              <div>
                <h4 className="font-medium text-xs text-muted-foreground">Real-time</h4>
                <p className="text-xs text-muted-foreground">
                  Instant updates
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scheduled sync options */}
      <AnimatePresence>
        {activeType === "scheduled" && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="space-y-3">
              {/* Frequency selection */}
              <div className="space-y-2">
                <h3 className="text-xs font-semibold text-foreground">Choose frequency</h3>
                <RadioGroup
                  value={value.frequency || "daily"}
                  onValueChange={handleFrequencyChange}
                  className="space-y-2"
                >
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Regular</div>
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="hourly" id="hourly" />
                          <Label htmlFor="hourly" className="cursor-pointer text-xs">Every hour</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="daily" id="daily" />
                          <Label htmlFor="daily" className="cursor-pointer text-xs">Every day</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="weekly" id="weekly" />
                          <Label htmlFor="weekly" className="cursor-pointer text-xs">Every week</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="monthly" id="monthly" />
                          <Label htmlFor="monthly" className="cursor-pointer text-xs">Every month</Label>
                        </div>
                        <div className="flex items-center space-x-2">
                          <RadioGroupItem value="custom" id="custom" />
                          <Label htmlFor="custom" className="cursor-pointer text-xs">Custom schedule</Label>
                        </div>
                      </div>
                    </div>
                    {supportsContinuous && (
                      <div className="space-y-1.5">
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Continuous sync</div>
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="every-5-min" id="every-5-min" />
                            <Label htmlFor="every-5-min" className="cursor-pointer flex items-center gap-1 text-xs">
                              Every 5 minutes
                              <Zap className="h-2.5 w-2.5 text-blue-600" />
                            </Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="every-15-min" id="every-15-min" />
                            <Label htmlFor="every-15-min" className="cursor-pointer flex items-center gap-1 text-xs">
                              Every 15 minutes
                              <Zap className="h-2.5 w-2.5 text-blue-600" />
                            </Label>
                          </div>
                          <div className="flex items-center space-x-2">
                            <RadioGroupItem value="every-30-min" id="every-30-min" />
                            <Label htmlFor="every-30-min" className="cursor-pointer flex items-center gap-1 text-xs">
                              Every 30 minutes
                              <Zap className="h-2.5 w-2.5 text-blue-600" />
                            </Label>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </RadioGroup>
              </div>

              {/* Time settings based on frequency */}
              <div className="space-y-2">

                {value.frequency === "hourly" && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="minute" className="text-xs font-medium">At minute:</Label>
                      <Select
                        value={String(value.minute || 0)}
                        onValueChange={(val) => handleTimeChange("minute", parseInt(val))}
                      >
                        <SelectTrigger id="minute" className="w-24 h-8">
                          <SelectValue placeholder="Minute" />
                        </SelectTrigger>
                        <SelectContent>
                          {Array.from({ length: 60 }).map((_, i) => (
                            <SelectItem key={i} value={String(i)}>
                              {i.toString().padStart(2, '0')}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                )}

                {(value.frequency === "daily" || value.frequency === "weekly" || value.frequency === "monthly") && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1">
                        <Label htmlFor="hour" className="text-xs font-medium">Hour</Label>
                        <Select
                          value={String(value.hour || 0)}
                          onValueChange={(val) => handleTimeChange("hour", parseInt(val))}
                        >
                          <SelectTrigger id="hour" className="h-8">
                            <SelectValue placeholder="Hour" />
                          </SelectTrigger>
                          <SelectContent>
                            {Array.from({ length: 24 }).map((_, i) => {
                              const localHour = i;
                              const tzOffsetHours = new Date().getTimezoneOffset() / 60;
                              const utcHour = (localHour + tzOffsetHours + 24) % 24;
                              return (
                                <SelectItem key={i} value={String(utcHour)}>
                                  {localHour.toString().padStart(2, '0')}:00
                                </SelectItem>
                              );
                            })}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor="minute" className="text-xs font-medium">Minute</Label>
                        <Select
                          value={String(value.minute || 0)}
                          onValueChange={(val) => handleTimeChange("minute", parseInt(val))}
                        >
                          <SelectTrigger id="minute" className="h-8">
                            <SelectValue placeholder="Minute" />
                          </SelectTrigger>
                          <SelectContent>
                            {Array.from({ length: 60 }).map((_, i) => (
                              <SelectItem key={i} value={String(i)}>
                                {i.toString().padStart(2, '0')}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  </div>
                )}

                {value.frequency === "weekly" && (
                  <div className="space-y-1">
                    <Label htmlFor="dayOfWeek" className="text-xs font-medium">Day of week</Label>
                    <Select
                      value={String(value.dayOfWeek || 1)}
                      onValueChange={(val) => handleTimeChange("dayOfWeek", parseInt(val))}
                    >
                      <SelectTrigger id="dayOfWeek" className="h-8">
                        <SelectValue placeholder="Select day" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="1">Monday</SelectItem>
                        <SelectItem value="2">Tuesday</SelectItem>
                        <SelectItem value="3">Wednesday</SelectItem>
                        <SelectItem value="4">Thursday</SelectItem>
                        <SelectItem value="5">Friday</SelectItem>
                        <SelectItem value="6">Saturday</SelectItem>
                        <SelectItem value="0">Sunday</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {value.frequency === "monthly" && (
                  <div className="space-y-1">
                    <Label htmlFor="dayOfMonth" className="text-xs font-medium">Day of month</Label>
                    <Select
                      value={String(value.dayOfMonth || 1)}
                      onValueChange={(val) => handleTimeChange("dayOfMonth", parseInt(val))}
                    >
                      <SelectTrigger id="dayOfMonth" className="h-8">
                        <SelectValue placeholder="Select day" />
                      </SelectTrigger>
                      <SelectContent>
                        {Array.from({ length: 31 }).map((_, i) => (
                          <SelectItem key={i} value={String(i + 1)}>
                            {i + 1}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {value.frequency === "custom" && (
                  <div className="space-y-2">
                    <Label className="text-xs font-medium">Custom cron expression</Label>
                    <div className="rounded-md bg-muted/50 p-3">
                      <CronExpressionInput
                        value={value.cronExpression || "* * * * *"}
                        onChange={(cronExp) => handleTimeChange("cronExpression", cronExp)}
                      />
                      {validationError && (
                        <p className="text-xs text-destructive mt-2">{validationError}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Show the generated cron expression for user reference */}
                {value.frequency !== "custom" && (
                  <div className="rounded-md bg-muted/30 p-2">
                    <div className="flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-green-500"></div>
                      <span className="text-xs font-medium text-muted-foreground">Schedule:</span>
                    </div>
                    <code className="text-xs font-mono text-foreground mt-1 block">
                      {buildCronExpression(value)}
                    </code>
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Re-export isValidCronExpression so it can be imported by other components
export { isValidCronExpression };
