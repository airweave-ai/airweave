import { client as defaultClient } from '../generated/client.gen';
import type * as z from 'zod';
import type { TDataShape } from '../generated/client';
import type { Options } from '../generated/sdk.gen';

interface CreateValidatedSseStreamParams<
  TEvent,
  TData extends TDataShape = TDataShape,
> {
  defaultSecurity?: Options<TData>['security'];
  isTerminal: (event: TEvent) => boolean;
  method?: 'get' | 'post';
  options: Options<TData>;
  schema: z.ZodType<TEvent>;
  url: TData['url'];
}

export async function createValidatedSseStream<
  TEvent,
  TData extends TDataShape = TDataShape,
>({
  defaultSecurity,
  isTerminal,
  method = 'get',
  options,
  schema,
  url,
}: CreateValidatedSseStreamParams<TEvent, TData>): Promise<
  AsyncIterable<TEvent>
> {
  const { client: requestClient, meta: _meta, ...requestOptions } = options;
  const client = requestClient ?? defaultClient;
  const { stream } = await client.sse[method]({
    ...requestOptions,
    security: requestOptions.security ?? defaultSecurity,
    url,
  });

  return (async function* () {
    for await (const chunk of stream as AsyncIterable<unknown>) {
      const event = schema.parse(chunk);

      yield event;

      if (isTerminal(event)) {
        return;
      }
    }

    const isAborted = requestOptions.signal?.aborted ?? false;

    if (!isAborted) {
      throw new Error('SSE stream ended before a terminal event was received');
    }
  })();
}
