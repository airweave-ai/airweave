export function getSourceDocsUrl(shortName: string) {
  return `https://docs.airweave.ai/docs/connectors/${shortName.replace(/_/g, '-')}`;
}
