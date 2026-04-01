const monoAppIconUrls = import.meta.glob('./apps/*.svg', {
  eager: true,
  import: 'default',
});

const colorAppIconUrls = import.meta.glob('./apps/color/*.svg', {
  eager: true,
  import: 'default',
});

type AppIconVariant = 'mono' | 'color';

function createIconUrlMap(iconUrls: Record<string, unknown>) {
  const appIconUrlByShortName: Record<string, string> = {};

  for (const [filePath, iconUrl] of Object.entries(iconUrls)) {
    if (typeof iconUrl !== 'string') {
      continue;
    }

    const fileName = filePath.split('/').pop() ?? '';
    appIconUrlByShortName[fileName.replace('.svg', '')] = iconUrl;
  }

  return appIconUrlByShortName;
}

const monoAppIconUrlByShortName = createIconUrlMap(monoAppIconUrls);
const colorAppIconUrlByShortName = createIconUrlMap(colorAppIconUrls);

export function getAppIconUrl(
  shortName: string,
  variant: AppIconVariant = 'mono',
) {
  if (variant === 'color') {
    return colorAppIconUrlByShortName[shortName] ?? null;
  }

  return monoAppIconUrlByShortName[shortName] ?? null;
}

export type { AppIconVariant };
