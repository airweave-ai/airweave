import { SettingsDialogLayout } from './settings-dialog-layout';

type SettingsDialogPlaceholderPageProps = {
  description: string;
  onClose: () => void;
  placeholder: string;
  title: string;
};

function SettingsDialogPlaceholderPage({
  description,
  onClose,
  placeholder,
  title,
}: SettingsDialogPlaceholderPageProps) {
  return (
    <SettingsDialogLayout
      title={title}
      description={description}
      onClose={onClose}
    >
      <div className="flex min-h-40 items-center justify-center rounded-lg border bg-foreground/[0.03] p-6 text-muted-foreground shadow-xs">
        {placeholder}
      </div>
    </SettingsDialogLayout>
  );
}

export { SettingsDialogPlaceholderPage };
