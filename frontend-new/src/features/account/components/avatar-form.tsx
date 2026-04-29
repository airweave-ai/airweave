import { AccountFormCard } from './account-form-card';
import type { AppSessionViewer } from '@/shared/session';
import { UserAvatar } from '@/shared/components/user-avatar';
import { Button } from '@/shared/ui/button';

type AvatarFormProps = {
  viewer: Pick<AppSessionViewer, 'email' | 'name' | 'picture'>;
};

function AvatarForm({ viewer }: AvatarFormProps) {
  return (
    <AccountFormCard
      title="Avatar"
      description="Avatar is your profile picture - everyone who visits your profile will see this."
      footer={
        <>
          <span className="flex-1" />
          <Button type="button" variant="secondary" size="lg" disabled>
            Save Changes
          </Button>
        </>
      }
    >
      <div className="flex items-center gap-4">
        <UserAvatar
          email={viewer.email}
          name={viewer.name}
          picture={viewer.picture}
          className="size-12"
        />

        <Button type="button" variant="outline" disabled>
          Upload
        </Button>
      </div>
    </AccountFormCard>
  );
}

export { AvatarForm };
