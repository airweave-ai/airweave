import * as React from 'react';
import { SelectionCard } from './selection-card';
import { withSourceConnectionForm } from './source-connection-form-hook';
import type { SourceConnectionFormInput } from './source-connection-form-hook';
import type { ConfigField, Source } from '@/shared/api';
import { DynamicConfigFieldInput } from '@/shared/config-fields';
import { FieldDescription, FieldTitle } from '@/shared/ui/field';
import { Switch } from '@/shared/ui/switch';

export const SourceConnectionConfigSection = withSourceConnectionForm({
  defaultValues: {} as SourceConnectionFormInput,
  props: {
    source: undefined as unknown as Source,
  },
  render: ({ form, source }) => {
    if (source.config_fields.fields.length === 0) {
      return null;
    }

    const requiredConfigFields = source.config_fields.fields.filter(
      (configField) => configField.required,
    );
    const optionalConfigFields = source.config_fields.fields.filter(
      (configField) => !configField.required,
    );

    return (
      <section className="space-y-6">
        {requiredConfigFields.map((configField) =>
          renderConfigField(form, configField),
        )}

        {optionalConfigFields.length > 0 ? (
          <OptionalConfigFieldsCard
            key={source.short_name}
            form={form}
            optionalConfigFields={optionalConfigFields}
            source={source}
          />
        ) : null}
      </section>
    );
  },
});

type SourceConnectionFormProp = React.ComponentProps<
  typeof SourceConnectionConfigSection
>['form'];

function OptionalConfigFieldsCard({
  form,
  optionalConfigFields,
  source,
}: {
  form: SourceConnectionFormProp;
  optionalConfigFields: Array<ConfigField>;
  source: Source;
}) {
  const [selected, setSelected] = React.useState(false);

  return (
    <SelectionCard
      header={
        <React.Fragment>
          <div className="space-y-1">
            <FieldTitle>Additional Configuration (Optional)</FieldTitle>
            <FieldDescription className="text-balance">
              By default, Airweave handles {source.name} sync for you.
              <br />
              Enable this to use your own custom {source.name} sync settings.
            </FieldDescription>
          </div>
          <Switch
            checked={selected}
            id="use-additional-configuration"
            onCheckedChange={(checked) => {
              setSelected(checked);

              if (checked) {
                return;
              }

              for (const configField of optionalConfigFields) {
                form.setFieldValue(
                  `config.${configField.name}`,
                  undefined as never,
                );
              }
            }}
          />
        </React.Fragment>
      }
      headerClassName="items-start justify-between"
      htmlFor="use-additional-configuration"
      selected={selected}
    >
      {optionalConfigFields.map((configField) =>
        renderConfigField(form, configField),
      )}
    </SelectionCard>
  );
}

function renderConfigField(
  form: SourceConnectionFormProp,
  configField: ConfigField,
) {
  return (
    <form.Field key={configField.name} name={`config.${configField.name}`}>
      {(field) => (
        <DynamicConfigFieldInput
          configField={configField}
          disabled={form.state.isSubmitting}
          errors={field.state.meta.errors}
          name={field.name}
          onBlur={field.handleBlur}
          onChange={field.handleChange}
          value={field.state.value}
        />
      )}
    </form.Field>
  );
}
