const numberFormatter = new Intl.NumberFormat();

export function formatNumber(value: number) {
  return numberFormatter.format(value);
}
