import { Link } from '@tanstack/react-router';
import type { LinkProps } from '@tanstack/react-router';
import type { SettingsPage } from '../layouts/app-search';

type SettingsLinkProps = React.ComponentProps<'a'> &
  Pick<LinkProps, 'replace'> & {
    page: SettingsPage;
  };

function SettingsLink({ page, children, ...props }: SettingsLinkProps) {
  return (
    <Link
      to="."
      search={(prev) => ({ ...prev, dialog: { type: 'settings', page } })}
      {...props}
    >
      {children}
    </Link>
  );
}

export { SettingsLink };
