import { intlFormatDistance, isValid, parseISO } from 'date-fns';

type DateValue = Date | string | null | undefined;

type RelativeDateFormatOptions = NonNullable<
  Parameters<typeof intlFormatDistance>[2]
>;

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
});

const timeFormatter = new Intl.DateTimeFormat(undefined, {
  timeStyle: 'short',
});

const utcTimestampFormatter = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  hour: '2-digit',
  hour12: false,
  minute: '2-digit',
  month: 'short',
  timeZone: 'UTC',
  timeZoneName: 'short',
  year: 'numeric',
});

export function parseDate(value: DateValue) {
  if (!value) {
    return null;
  }

  if (value instanceof Date) {
    return isValid(value) ? value : null;
  }

  const normalizedValue = hasTimezoneSuffix(value) ? value : `${value}Z`;
  const parsedIsoDate = parseISO(normalizedValue);

  if (isValid(parsedIsoDate)) {
    return parsedIsoDate;
  }

  const parsedDate = new Date(normalizedValue);

  if (isValid(parsedDate)) {
    return parsedDate;
  }

  return null;
}

export function formatDate(value: DateValue) {
  const date = parseDate(value);

  return date ? dateFormatter.format(date) : null;
}

export function formatTime(value: DateValue) {
  const date = parseDate(value);

  return date ? timeFormatter.format(date) : null;
}

export function formatRelativeDate(
  value: DateValue,
  options?: RelativeDateFormatOptions,
) {
  const date = parseDate(value);

  if (!date) {
    return null;
  }

  return intlFormatDistance(date, new Date(), options);
}

export function formatUtcTimestamp(value: DateValue) {
  const date = parseDate(value);

  return date ? utcTimestampFormatter.format(date) : null;
}

function hasTimezoneSuffix(value: string) {
  return /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
}
