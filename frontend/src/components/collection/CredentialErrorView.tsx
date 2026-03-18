import React, { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, KeyRound, ExternalLink, ShieldAlert, Unplug, Trash2, Loader2, Eye, EyeOff, RotateCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { getAppIconUrl } from '@/lib/utils/icons';
import { DESIGN_SYSTEM } from '@/lib/design-system';
import { apiClient } from '@/lib/api';
import { toast } from '@/hooks/use-toast';

type ErrorCategory =
  | 'oauth_credentials_expired'
  | 'api_key_invalid'
  | 'client_credentials_invalid'
  | 'auth_provider_account_gone'
  | 'auth_provider_credentials_invalid';

interface SourceConnection {
  id: string;
  name: string;
  short_name: string;
  error_category?: string;
  error_message?: string;
  auth?: {
    method?: string;
    authenticated?: boolean;
    auth_url?: string;
    provider_readable_id?: string;
    provider_settings_url?: string;
  };
}

interface CredentialErrorViewProps {
  sourceConnection: SourceConnection;
  onRefreshAuthUrl?: () => void;
  isRefreshing?: boolean;
  onDelete?: () => void;
  onCredentialsUpdated?: () => void;
}

interface AuthField {
  name: string;
  label: string;
  type: string;
  required: boolean;
  secret: boolean;
}

const CATEGORY_CONFIG: Record<ErrorCategory, {
  icon: React.ElementType;
  title: string;
  iconColor: { dark: string; light: string };
  borderColor: { dark: string; light: string };
  bgColor: { dark: string; light: string };
}> = {
  oauth_credentials_expired: {
    icon: ShieldAlert,
    title: 'Re-authorization Required',
    iconColor: { dark: 'text-amber-400', light: 'text-amber-600' },
    borderColor: { dark: 'border-amber-800/30', light: 'border-amber-200' },
    bgColor: { dark: 'bg-amber-900/10', light: 'bg-amber-50' },
  },
  api_key_invalid: {
    icon: KeyRound,
    title: 'API Key Invalid',
    iconColor: { dark: 'text-red-400', light: 'text-red-600' },
    borderColor: { dark: 'border-red-800/30', light: 'border-red-200' },
    bgColor: { dark: 'bg-red-900/10', light: 'bg-red-50' },
  },
  client_credentials_invalid: {
    icon: KeyRound,
    title: 'Client Credentials Invalid',
    iconColor: { dark: 'text-red-400', light: 'text-red-600' },
    borderColor: { dark: 'border-red-800/30', light: 'border-red-200' },
    bgColor: { dark: 'bg-red-900/10', light: 'bg-red-50' },
  },
  auth_provider_account_gone: {
    icon: Unplug,
    title: 'Auth Provider Account Not Found',
    iconColor: { dark: 'text-orange-400', light: 'text-orange-600' },
    borderColor: { dark: 'border-orange-800/30', light: 'border-orange-200' },
    bgColor: { dark: 'bg-orange-900/10', light: 'bg-orange-50' },
  },
  auth_provider_credentials_invalid: {
    icon: ShieldAlert,
    title: 'Auth Provider Credentials Invalid',
    iconColor: { dark: 'text-orange-400', light: 'text-orange-600' },
    borderColor: { dark: 'border-orange-800/30', light: 'border-orange-200' },
    bgColor: { dark: 'bg-orange-900/10', light: 'bg-orange-50' },
  },
};

export const CredentialErrorView: React.FC<CredentialErrorViewProps> = ({
  sourceConnection,
  onRefreshAuthUrl,
  isRefreshing = false,
  onDelete,
  onCredentialsUpdated,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';
  const category = sourceConnection.error_category as ErrorCategory | undefined;

  if (!category || !(category in CATEGORY_CONFIG)) {
    return null;
  }

  const config = CATEGORY_CONFIG[category];
  const Icon = config.icon;

  return (
    <div className={cn(
      'rounded-xl border p-5 space-y-4',
      config.borderColor[isDark ? 'dark' : 'light'],
      config.bgColor[isDark ? 'dark' : 'light'],
    )}>
      {/* Header: icon + title + message + source icon */}
      <div className="flex items-start gap-3">
        <div className={cn(
          'flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center',
          isDark ? 'bg-gray-800/60' : 'bg-white shadow-sm',
        )}>
          <Icon className={cn('h-5 w-5', config.iconColor[isDark ? 'dark' : 'light'])} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className={cn(
            DESIGN_SYSTEM.typography.sizes.header,
            DESIGN_SYSTEM.typography.weights.semibold,
            'mb-1',
            isDark ? 'text-gray-100' : 'text-gray-900',
          )}>
            {config.title}
          </h3>
          <p className={cn(
            DESIGN_SYSTEM.typography.sizes.body,
            isDark ? 'text-gray-400' : 'text-gray-600',
          )}>
            {sourceConnection.error_message}
          </p>
        </div>
        {sourceConnection.short_name && (
          <img
            src={getAppIconUrl(sourceConnection.short_name, resolvedTheme)}
            alt={sourceConnection.name}
            className="h-8 w-8 rounded-md object-contain flex-shrink-0 opacity-40"
            onError={(e) => { e.currentTarget.style.display = 'none'; }}
          />
        )}
      </div>

      {/* Action area + delete — differs per category */}
      <ActionArea
        category={category}
        sourceConnection={sourceConnection}
        isDark={isDark}
        onRefreshAuthUrl={onRefreshAuthUrl}
        isRefreshing={isRefreshing}
        onCredentialsUpdated={onCredentialsUpdated}
        onDelete={onDelete}
      />
    </div>
  );
};

function DeleteButton({ onDelete, isDark }: { onDelete?: () => void; isDark: boolean }) {
  if (!onDelete) return null;
  return (
    <button
      onClick={onDelete}
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-2 rounded-lg',
        DESIGN_SYSTEM.typography.sizes.body,
        DESIGN_SYSTEM.typography.weights.medium,
        'transition-all duration-200',
        isDark
          ? 'text-gray-400 hover:text-red-400 hover:bg-red-900/20'
          : 'text-gray-500 hover:text-red-600 hover:bg-red-50',
      )}
    >
      <Trash2 className="h-3.5 w-3.5" />
      Delete connection
    </button>
  );
}

function ActionArea({
  category,
  sourceConnection,
  isDark,
  onRefreshAuthUrl,
  isRefreshing,
  onCredentialsUpdated,
  onDelete,
}: {
  category: ErrorCategory;
  sourceConnection: SourceConnection;
  isDark: boolean;
  onRefreshAuthUrl?: () => void;
  isRefreshing?: boolean;
  onCredentialsUpdated?: () => void;
  onDelete?: () => void;
}) {
  const buttonBase = cn(
    'inline-flex items-center gap-2 px-4 py-2 rounded-lg',
    DESIGN_SYSTEM.typography.sizes.body,
    DESIGN_SYSTEM.typography.weights.medium,
    'transition-all duration-200 shadow-sm',
  );

  const primaryStyle = cn(
    buttonBase,
    'bg-primary text-primary-foreground hover:bg-primary/90',
  );

  const secondaryStyle = cn(
    buttonBase,
    isDark
      ? 'bg-gray-800 text-gray-200 hover:bg-gray-700 border border-gray-600'
      : 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-200',
  );

  switch (category) {
    case 'oauth_credentials_expired':
      return (
        <div className="flex items-center gap-2 pt-1">
          <button
            onClick={onRefreshAuthUrl}
            disabled={isRefreshing}
            className={primaryStyle}
          >
            {isRefreshing ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RotateCw className="h-3.5 w-3.5" />
            )}
            Reauthenticate
          </button>
          <DeleteButton onDelete={onDelete} isDark={isDark} />
        </div>
      );

    case 'api_key_invalid':
    case 'client_credentials_invalid':
      return (
        <InlineCredentialForm
          sourceConnection={sourceConnection}
          isDark={isDark}
          onCredentialsUpdated={onCredentialsUpdated}
          onDelete={onDelete}
        />
      );

    case 'auth_provider_account_gone': {
      const settingsUrl = sourceConnection.auth?.provider_settings_url;
      const providerId = sourceConnection.auth?.provider_readable_id;
      const providerName = providerId?.split('-')[0];

      return (
        <div className="flex items-center gap-2 pt-1">
          {settingsUrl && (
            <a
              href={settingsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={secondaryStyle}
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Open {providerName ? capitalise(providerName) : 'Provider'} Dashboard
            </a>
          )}
          <a href="/auth-providers" className={primaryStyle}>
            <ShieldAlert className="h-3.5 w-3.5" />
            Auth Providers Settings
          </a>
          <DeleteButton onDelete={onDelete} isDark={isDark} />
        </div>
      );
    }

    case 'auth_provider_credentials_invalid':
      return (
        <div className="flex items-center gap-2 pt-1">
          <a href="/auth-providers" className={primaryStyle}>
            <ShieldAlert className="h-3.5 w-3.5" />
            Auth Providers Settings
          </a>
          <DeleteButton onDelete={onDelete} isDark={isDark} />
        </div>
      );

    default:
      return null;
  }
}

function InlineCredentialForm({
  sourceConnection,
  isDark,
  onCredentialsUpdated,
  onDelete,
}: {
  sourceConnection: SourceConnection;
  isDark: boolean;
  onCredentialsUpdated?: () => void;
  onDelete?: () => void;
}) {
  const [fields, setFields] = useState<AuthField[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const fetchFields = useCallback(async () => {
    try {
      const resp = await apiClient.get(`/sources/${sourceConnection.short_name}`);
      const data = await resp.json();
      const raw = data?.auth_fields?.fields ?? [];
      const parsed: AuthField[] = raw.map((f: any) => ({
        name: f.name,
        label: f.label || f.name,
        type: f.type || 'string',
        required: f.required ?? true,
        secret: f.secret ?? false,
      }));
      setFields(parsed);
    } catch {
      setFields([]);
    } finally {
      setLoading(false);
    }
  }, [sourceConnection.short_name]);

  useEffect(() => { fetchFields(); }, [fetchFields]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const resp = await apiClient.patch(`/source-connections/${sourceConnection.id}`, {
        authentication: { credentials: values },
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${resp.status}`);
      }
      toast({ title: 'Credentials updated', description: 'Connection will be retried on next sync.' });
      onCredentialsUpdated?.();
    } catch (err: any) {
      toast({
        title: 'Update failed',
        description: err?.message || 'Could not update credentials.',
        variant: 'destructive',
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2">
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        <span className={cn(DESIGN_SYSTEM.typography.sizes.body, 'text-muted-foreground')}>
          Loading credential fields…
        </span>
      </div>
    );
  }

  if (fields.length === 0) {
    return (
      <p className={cn(DESIGN_SYSTEM.typography.sizes.body, 'text-muted-foreground italic')}>
        No credential fields found for this source. You may need to delete and recreate the connection.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {fields.map((field) => {
        const isSecret = field.secret;
        const visible = showSecrets[field.name];
        const displayLabel = humanizeFieldName(field.label || field.name);
        return (
          <div key={field.name} className="space-y-1.5">
            <label
              htmlFor={`cred-${field.name}`}
              className={cn(
                'text-xs font-medium tracking-wide uppercase',
                isDark ? 'text-gray-400' : 'text-gray-500',
              )}
            >
              {displayLabel}
            </label>
            <div className="relative">
              <input
                id={`cred-${field.name}`}
                type={isSecret && !visible ? 'password' : 'text'}
                required={field.required}
                value={values[field.name] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [field.name]: e.target.value }))}
                placeholder={isSecret ? '••••••••' : `Enter ${displayLabel.toLowerCase()}`}
                className={cn(
                  'w-full rounded-lg border px-3 py-2.5 pr-10',
                  DESIGN_SYSTEM.typography.sizes.body,
                  isDark
                    ? 'bg-gray-900/60 border-gray-700 text-gray-100 placeholder:text-gray-600'
                    : 'bg-white border-gray-200 text-gray-900 placeholder:text-gray-400',
                  'focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary/40',
                  'transition-colors duration-150',
                )}
              />
              {isSecret && (
                <button
                  type="button"
                  onClick={() => setShowSecrets((s) => ({ ...s, [field.name]: !s[field.name] }))}
                  className={cn(
                    'absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded-md',
                    'transition-colors duration-150',
                    isDark ? 'text-gray-500 hover:text-gray-300 hover:bg-gray-800' : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100',
                  )}
                >
                  {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              )}
            </div>
          </div>
        );
      })}
      <div className="flex items-center gap-2 pt-1">
        <button
          type="submit"
          disabled={submitting}
          className={cn(
            'inline-flex items-center gap-2 px-4 py-2 rounded-lg shadow-sm',
            DESIGN_SYSTEM.typography.sizes.body,
            DESIGN_SYSTEM.typography.weights.medium,
            'transition-all duration-200',
            'bg-primary text-primary-foreground hover:bg-primary/90',
            submitting && 'opacity-60 cursor-not-allowed',
          )}
        >
          {submitting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <KeyRound className="h-3.5 w-3.5" />
          )}
          Update Credentials
        </button>
        <DeleteButton onDelete={onDelete} isDark={isDark} />
      </div>
    </form>
  );
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function humanizeFieldName(name: string): string {
  return name
    .replace(/[_-]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
