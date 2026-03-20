/**
 * Utility to parse cron expressions and return human-readable descriptions
 */

import cronstrue from 'cronstrue';

export interface ParsedCron {
  description: string;
  shortDescription: string;
  descriptionLocal: string;
  shortDescriptionLocal: string;
}

/**
 * Parse a cron expression and return a human-readable description
 * @param cronExpression - The cron expression to parse (5 parts: minute hour day month weekday)
 * @returns Parsed cron with descriptions, or null if invalid
 */
export function parseCronExpression(cronExpression: string | undefined | null): ParsedCron | null {
  if (!cronExpression) return null;

  const parts = cronExpression.trim().split(/\s+/);
  if (parts.length !== 5) return null;

  let description: string;
  try {
    description = cronstrue.toString(cronExpression, { use24HourTimeFormat: false });
  } catch {
    return null;
  }

  const descriptionLocal = buildLocalDescription(parts, description);
  const shortDescription = shorten(description);
  const shortDescriptionLocal = shorten(descriptionLocal);

  return { description, shortDescription, descriptionLocal, shortDescriptionLocal };
}

/**
 * Build a local-time description by converting UTC hour/minute fields to local time.
 * For frequency-only schedules (every N minutes/hours), local and UTC are the same.
 */
function buildLocalDescription(parts: string[], utcDescription: string): string {
  const [minute, hour] = parts;

  // If there's no fixed hour, local time == UTC (frequency-based schedule)
  if (hour === '*' || hour.startsWith('*/')) return utcDescription;

  const hourNum = parseInt(hour, 10);
  const minuteNum = parseInt(minute, 10);
  if (isNaN(hourNum) || isNaN(minuteNum)) return utcDescription;

  const local = toLocalTime(hourNum, minuteNum);
  const localTimeStr = formatTime12(local.hour, local.minute);
  const utcTimeStr = formatTime12(hourNum, minuteNum);

  // Replace the UTC time string with the local one
  return utcDescription.replace(utcTimeStr, localTimeStr);
}

function toLocalTime(utcHour: number, utcMinute: number): { hour: number; minute: number } {
  const d = new Date();
  d.setUTCHours(utcHour, utcMinute, 0, 0);
  return { hour: d.getHours(), minute: d.getMinutes() };
}

function formatTime12(hour: number, minute: number): string {
  const period = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  const minuteStr = minute.toString().padStart(2, '0');
  return `${displayHour}:${minuteStr} ${period}`;
}

/**
 * Create a condensed short description from a full cronstrue description.
 */
function shorten(desc: string): string {
  // "Every minute"
  if (/^every minute$/i.test(desc)) return 'Every min';

  // "Every N minutes"
  const everyNMin = desc.match(/^every (\d+) minutes?$/i);
  if (everyNMin) return `Every ${everyNMin[1]}m`;

  // "Every hour"
  if (/^every hour$/i.test(desc)) return 'Hourly';

  // "Every N hours"
  const everyNHr = desc.match(/^every (\d+) hours?$/i);
  if (everyNHr) return `Every ${everyNHr[1]}h`;

  // "Every hour, at HH:MM" → "Hourly :MM"
  const hourlyAt = desc.match(/^every hour,? at (\d+):(\d+)/i);
  if (hourlyAt) return `Hourly :${hourlyAt[2]}`;

  // "At HH:MM PM, ..." with day info → extract time + context
  const atTime = desc.match(/at (\d+:\d+ [AP]M)/i);

  // Daily
  if (/every day/i.test(desc) && atTime) return `Daily ${atTime[1].toLowerCase()}`;

  // Weekly (contains a day name)
  const dayMatch = desc.match(/\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b/i);
  if (dayMatch && atTime) return `${dayMatch[1]}s ${atTime[1].toLowerCase()}`;

  // Monthly
  if (/day \d+ of the month/i.test(desc) && atTime) {
    const dayNum = desc.match(/day (\d+)/i);
    if (dayNum) {
      const ordinal = toOrdinal(parseInt(dayNum[1], 10));
      return `Monthly ${ordinal}`;
    }
  }

  // Fallback: truncate if too long
  return desc.length > 20 ? desc.slice(0, 18) + '...' : desc;
}

function toOrdinal(n: number): string {
  if (n === 1) return '1st';
  if (n === 2) return '2nd';
  if (n === 3) return '3rd';
  return `${n}th`;
}

/**
 * Format time until next run
 */
export function formatTimeUntil(nextRun: Date | string | undefined | null): string {
  if (!nextRun) return '';

  const nextRunDate = typeof nextRun === 'string' ? new Date(nextRun) : nextRun;
  const now = new Date();
  const diffMs = nextRunDate.getTime() - now.getTime();

  if (diffMs < 0) return 'Now';

  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays > 0) {
    return `in ${diffDays}d`;
  } else if (diffHrs > 0) {
    const mins = diffMins % 60;
    return mins > 0 ? `in ${diffHrs}h ${mins}m` : `in ${diffHrs}h`;
  } else if (diffMins > 0) {
    return `in ${diffMins}m`;
  } else {
    return 'in <1m';
  }
}
