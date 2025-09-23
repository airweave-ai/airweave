import React from 'react';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-provider';
import { AuthMode } from '@/stores/collectionCreationStore';

interface AuthMethodSelectorProps {
  selectedMethod: AuthMode | undefined;
  onMethodChange: (method: AuthMode) => void;
  availableAuthMethods: AuthMode[];
}

export const AuthMethodSelector: React.FC<AuthMethodSelectorProps> = ({
  selectedMethod,
  onMethodChange,
  availableAuthMethods,
}) => {
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === 'dark';

  // Don't show selector if only one method available
  if (availableAuthMethods.length <= 1) {
    return null;
  }

  const methodInfo: Record<AuthMode, { label: string }> = {
    direct_auth: {
      label: 'Direct Credentials',
    },
    oauth2: {
      label: 'OAuth Connection',
    },
    external_provider: {
      label: 'Use Auth Provider',
    },
    config_auth: {
      label: 'Configuration',
    },
  };

  return (
    <div className="space-y-2">
      <label className="block text-xs text-gray-500 dark:text-gray-400 uppercase tracking-wider">
        Authentication Method
      </label>

      <RadioGroup
        value={selectedMethod}
        onValueChange={(value) => onMethodChange(value as AuthMode)}
        className="space-y-2"
      >
        {availableAuthMethods.map((method) => {
          const info = methodInfo[method];

          return (
            <label
              key={method}
              className={cn(
                "flex items-start gap-3 p-2.5 rounded-lg border cursor-pointer transition-all",
                selectedMethod === method
                  ? isDark
                    ? "border-blue-500/50 bg-blue-500/10"
                    : "border-blue-500/50 bg-blue-50/50"
                  : isDark
                    ? "border-gray-800 hover:border-gray-700 bg-gray-900/30"
                    : "border-gray-200 hover:border-gray-300 bg-white"
              )}
            >
              <RadioGroupItem
                value={method}
                className="mt-0.5"
              />
              <div className={cn(
                "text-sm",
                isDark ? "text-gray-200" : "text-gray-700"
              )}>
                {info.label}
              </div>
            </label>
          );
        })}
      </RadioGroup>
    </div>
  );
};
