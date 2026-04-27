import { ArrowUpRight } from 'lucide-react';
import { Button } from '@/shared/ui/button';

const authProviderSettingsLinks = {
  composio: {
    href: 'https://platform.composio.dev/',
    label: 'Get API Key from Composio',
  },
  pipedream: {
    href: 'https://pipedream.com/settings/api',
    label: 'Get Client ID & Secret from Pipedream',
  },
} as const;

type AuthProviderSettingsLinkProps = {
  shortName: string;
};

export function AuthProviderSettingsLink({
  shortName,
}: AuthProviderSettingsLinkProps) {
  const settingsLink = getAuthProviderSettingsLink(shortName);

  if (settingsLink === null) {
    return null;
  }

  return (
    <Button asChild className="w-fit" variant="outline">
      <a href={settingsLink.href} rel="noreferrer" target="_blank">
        {settingsLink.label}
        <ArrowUpRight className="size-4" />
      </a>
    </Button>
  );
}

function getAuthProviderSettingsLink(shortName: string) {
  if (!(shortName in authProviderSettingsLinks)) {
    return null;
  }

  return authProviderSettingsLinks[
    shortName as keyof typeof authProviderSettingsLinks
  ];
}
