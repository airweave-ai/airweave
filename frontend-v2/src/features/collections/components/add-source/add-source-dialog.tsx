/**
 * AddSourceDialog - Multi-step dialog for adding a source to a collection
 */

import { useCallback } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAddSourceStore } from "@/stores/add-source-store";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";

import { SourceConfigView } from "./source-config-view";
import { SourceSelectView } from "./source-select-view";
import { SuccessView } from "./success-view";

interface AddSourceDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddSourceDialog({ open, onOpenChange }: AddSourceDialogProps) {
  const {
    currentStep,
    collectionId,
    collectionName,
    selectedSourceShortName,
    selectedSourceName,
    connectionName,
    authMode,
    authFields,
    configFields,
    useCustomOAuth,
    clientId,
    clientSecret,
    selectSource,
    setStep,
    goBack,
    setConnectionName,
    setAuthMode,
    setAuthField,
    setConfigField,
    setUseCustomOAuth,
    setClientId,
    setClientSecret,
    completeWithOAuth,
    completeWithoutOAuth,
    reset,
    close,
  } = useAddSourceStore();

  const handleOpenChange = useCallback(
    (newOpen: boolean) => {
      if (!newOpen) {
        close();
        setTimeout(() => {
          reset();
        }, 300);
      }
      onOpenChange(newOpen);
    },
    [close, reset, onOpenChange]
  );

  const handleSelectSource = useCallback(
    (shortName: string, displayName: string) => {
      selectSource(shortName, displayName);
    },
    [selectSource]
  );

  const handleConnectionSuccess = useCallback(
    (connectionId: string, oauthUrl?: string) => {
      if (oauthUrl) {
        completeWithOAuth(connectionId, oauthUrl);
      } else {
        completeWithoutOAuth(connectionId);
      }
    },
    [completeWithOAuth, completeWithoutOAuth]
  );

  const handleCancel = useCallback(() => {
    handleOpenChange(false);
  }, [handleOpenChange]);

  const handleBack = useCallback(() => {
    goBack();
  }, [goBack]);

  const getDialogSize = () => {
    switch (currentStep) {
      case "source-select":
        return "max-w-4xl";
      case "source-config":
      case "oauth-pending":
        return "max-w-lg";
      case "success":
        return "max-w-md";
      default:
        return "max-w-2xl";
    }
  };

  const renderContent = () => {
    if (!collectionId || !collectionName) {
      return null;
    }

    switch (currentStep) {
      case "source-select":
        return (
          <SourceSelectView
            onSelectSource={handleSelectSource}
            onCancel={handleCancel}
          />
        );

      case "source-config":
      case "oauth-pending":
        if (!selectedSourceShortName || !selectedSourceName) {
          // Should not happen, but handle gracefully
          setStep("source-select");
          return null;
        }
        return (
          <SourceConfigView
            collectionId={collectionId}
            collectionName={collectionName}
            sourceShortName={selectedSourceShortName}
            sourceName={selectedSourceName}
            connectionName={connectionName}
            authMode={authMode}
            authFields={authFields}
            configFields={configFields}
            useCustomOAuth={useCustomOAuth}
            clientId={clientId}
            clientSecret={clientSecret}
            onBack={handleBack}
            onConnectionNameChange={setConnectionName}
            onAuthModeChange={setAuthMode}
            onAuthFieldChange={setAuthField}
            onConfigFieldChange={setConfigField}
            onUseCustomOAuthChange={setUseCustomOAuth}
            onClientIdChange={setClientId}
            onClientSecretChange={setClientSecret}
            onSuccess={handleConnectionSuccess}
            onCancel={handleCancel}
          />
        );

      case "success":
        return (
          <SuccessView
            collectionId={collectionId}
            collectionName={collectionName}
            sourceName={selectedSourceName || "Source"}
            onClose={handleCancel}
          />
        );

      default:
        return null;
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className={`${getDialogSize()} h-[600px] overflow-hidden p-0`}
        // Prevent closing when clicking outside during OAuth flow
        onPointerDownOutside={(e) => {
          if (currentStep === "oauth-pending") {
            e.preventDefault();
          }
        }}
        // Prevent closing with escape during OAuth flow
        onEscapeKeyDown={(e) => {
          if (currentStep === "oauth-pending") {
            e.preventDefault();
          }
        }}
      >
        <VisuallyHidden>
          <DialogTitle>Add Source to Collection</DialogTitle>
          <DialogDescription>
            Select and configure a data source to connect to your collection
          </DialogDescription>
        </VisuallyHidden>
        {renderContent()}
      </DialogContent>
    </Dialog>
  );
}
