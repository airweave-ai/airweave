import { AccountFormCard } from './account-form-card';
import { Button } from '@/shared/ui/button';

function DeleteAccountForm() {
  return (
    <AccountFormCard
      title="Delete account"
      description="This will permanently delete your Personal Account. Please note that this action is irreversible, so proceed with caution."
      footer={
        <>
          <p className="text-sm text-destructive">
            This action cannot be undone!
          </p>

          <Button type="button" variant="destructive" disabled>
            Delete account
          </Button>
        </>
      }
    />
  );
}

export { DeleteAccountForm };
