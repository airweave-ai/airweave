const countFormatter = new Intl.NumberFormat();

export function formatCount(value: number) {
  return countFormatter.format(value);
}
