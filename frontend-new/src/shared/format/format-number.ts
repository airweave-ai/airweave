const numberFormatter = new Intl.NumberFormat();

export function formatNumber(
  value: number,
  options?: Intl.NumberFormatOptions,
) {
  if (options) {
    return new Intl.NumberFormat(undefined, options).format(value);
  }

  return numberFormatter.format(value);
}
