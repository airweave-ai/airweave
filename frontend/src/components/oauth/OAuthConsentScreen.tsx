import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Shield, AlertCircle } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface Collection {
  id: string;
  name: string;
  readable_id: string;
}

interface OAuthConsentScreenProps {
  clientName: string;
  requestedScopes: string[];
  collections: Collection[];
  onApprove: (collectionId: string) => void;
  onDeny: () => void;
  isLoading?: boolean;
}

export const OAuthConsentScreen: React.FC<OAuthConsentScreenProps> = ({
  clientName,
  requestedScopes,
  collections,
  onApprove,
  onDeny,
  isLoading = false,
}) => {
  const [selectedCollectionId, setSelectedCollectionId] = useState<string>('');

  useEffect(() => {
    // Auto-select first collection if only one available
    if (collections.length === 1) {
      setSelectedCollectionId(collections[0].id);
    }
  }, [collections]);

  const handleApprove = () => {
    if (selectedCollectionId) {
      onApprove(selectedCollectionId);
    }
  };

  const getScopeDescription = (scope: string): string => {
    const descriptions: Record<string, string> = {
      'read:collection': 'Search and read data from your collection',
      'write:collection': 'Add or modify data in your collection',
    };
    return descriptions[scope] || scope;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-4">
      <Card className="w-full max-w-md p-8">
        {/* Security indicator */}
        <div className="flex items-center justify-center mb-6">
          <div className="p-3 bg-blue-100 dark:bg-blue-900 rounded-full">
            <Shield className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-center mb-2">
          Authorize {clientName}
        </h1>
        <p className="text-sm text-gray-600 dark:text-gray-400 text-center mb-6">
          {clientName} wants to access your Airweave data
        </p>

        {/* Permissions */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold mb-3">This application will be able to:</h2>
          <ul className="space-y-2">
            {requestedScopes.map((scope) => (
              <li key={scope} className="flex items-start">
                <span className="mr-2 text-green-600">✓</span>
                <span className="text-sm">{getScopeDescription(scope)}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Collection selector */}
        <div className="mb-6">
          <label className="block text-sm font-semibold mb-2">
            Select a collection
          </label>
          <Select value={selectedCollectionId} onValueChange={setSelectedCollectionId}>
            <SelectTrigger>
              <SelectValue placeholder="Choose a collection..." />
            </SelectTrigger>
            <SelectContent>
              {collections.map((collection) => (
                <SelectItem key={collection.id} value={collection.id}>
                  {collection.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-gray-500 mt-1">
            {clientName} will only have access to this collection
          </p>
        </div>

        {/* Warning */}
        <Alert className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="text-xs">
            Only authorize applications you trust. You can revoke access at any time from
            your account settings.
          </AlertDescription>
        </Alert>

        {/* Action buttons */}
        <div className="flex gap-3">
          <Button
            variant="outline"
            className="flex-1"
            onClick={onDeny}
            disabled={isLoading}
          >
            Deny
          </Button>
          <Button
            className="flex-1"
            onClick={handleApprove}
            disabled={!selectedCollectionId || isLoading}
          >
            {isLoading ? 'Authorizing...' : 'Authorize'}
          </Button>
        </div>

        {/* Security notice */}
        <p className="text-xs text-center text-gray-500 mt-6">
          By authorizing, you agree to share data from the selected collection with{' '}
          {clientName}.
        </p>
      </Card>
    </div>
  );
};
