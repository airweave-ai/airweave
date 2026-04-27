const authProviderIconUrls = import.meta.glob(
  './auth-providers/*.{svg,png,jpeg,jpg}',
  {
    eager: true,
    import: 'default',
  },
);

function createIconUrlMap(iconUrls: Record<string, unknown>) {
  const authProviderIconUrlByShortName: Record<string, string> = {};

  for (const [filePath, iconUrl] of Object.entries(iconUrls)) {
    if (typeof iconUrl !== 'string') {
      continue;
    }

    const fileName = filePath.split('/').pop() ?? '';
    authProviderIconUrlByShortName[fileName.replace(/\.[^.]+$/, '')] = iconUrl;
  }

  return authProviderIconUrlByShortName;
}

const authProviderIconUrlByShortName = createIconUrlMap(authProviderIconUrls);

export function getAuthProviderIconUrl(shortName: string) {
  return authProviderIconUrlByShortName[shortName] ?? null;
}
