import {
  createFormHook,
  createFormHookContexts,
  formOptions,
} from '@tanstack/react-form';
import { defaultCollectionSearchFormValues } from '../../lib/collection-search-model';
import { collectionSearchFormSchema } from '../../lib/collection-search-schema';
import type { CollectionSearchFormValues } from '../../lib/collection-search-model';

const { fieldContext, formContext } = createFormHookContexts();

const baseCollectionSearchFormOptions = {
  defaultValues: defaultCollectionSearchFormValues,
  validators: {
    onChange: collectionSearchFormSchema,
    onMount: collectionSearchFormSchema,
    onSubmit: collectionSearchFormSchema,
  },
} as const;

export const collectionSearchFormOptions = formOptions({
  ...baseCollectionSearchFormOptions,
});

export const { useAppForm: useCollectionSearchForm } = createFormHook({
  fieldComponents: {},
  fieldContext,
  formComponents: {},
  formContext,
});

export function getCollectionSearchFormOptions({
  onSubmit,
}: {
  onSubmit: (values: CollectionSearchFormValues) => void;
}) {
  return formOptions({
    ...collectionSearchFormOptions,
    onSubmit: ({ value }) => {
      onSubmit(value);
    },
  });
}
