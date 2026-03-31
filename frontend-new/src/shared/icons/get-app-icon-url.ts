const appIconUrls = import.meta.glob('./apps/*.svg', {
  eager: true,
  import: 'default',
});

const appIconUrlByShortName: Record<string, string> = {};

for (const [filePath, iconUrl] of Object.entries(appIconUrls)) {
  if (typeof iconUrl !== 'string') {
    continue;
  }

  const fileName = filePath.split('/').pop() ?? '';
  appIconUrlByShortName[fileName.replace('.svg', '')] = iconUrl;
}

// TODO: update default-icon
const defaultAppIconUrl = appIconUrlByShortName['default-icon']!;

export function getAppIconUrl(shortName: string) {
  return appIconUrlByShortName[shortName] ?? defaultAppIconUrl;
}
