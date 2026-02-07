// Theme types for customization
export type ThemeMode = "dark" | "light" | "system";

export interface ThemeColors {
  background?: string;
  surface?: string;
  text?: string;
  textMuted?: string;
  primary?: string;
  primaryForeground?: string;
  primaryHover?: string;
  secondary?: string;
  secondaryHover?: string;
  border?: string;
  success?: string;
  error?: string;
}

export interface ThemeFonts {
  /** Google Font family name for body text (e.g., "Inter", "Open Sans") */
  body?: string;
  /** Google Font family name for headings (e.g., "Poppins", "Montserrat") */
  heading?: string;
  /** Google Font family name for buttons. If not specified, inherits from body */
  button?: string;
}

export interface ConnectLabels {
  // Main headings
  sourcesHeading?: string;

  // Connection status labels
  statusActive?: string;
  statusSyncing?: string;
  statusPendingAuth?: string;
  statusError?: string;
  statusInactive?: string;

  // Connection item
  entitiesCount?: string; // Use {count} placeholder, e.g. "{count} entities"

  // Menu actions
  menuReconnect?: string;
  menuDelete?: string;

  // Empty state
  emptyStateHeading?: string;
  emptyStateDescription?: string;

  // Connect mode error
  connectModeErrorHeading?: string;
  connectModeErrorDescription?: string;

  // Load error
  loadErrorHeading?: string;

  // Error screen titles
  errorInvalidTokenTitle?: string;
  errorExpiredTokenTitle?: string;
  errorNetworkTitle?: string;
  errorSessionMismatchTitle?: string;
  errorDefaultTitle?: string;

  // Error screen descriptions
  errorInvalidTokenDescription?: string;
  errorExpiredTokenDescription?: string;
  errorNetworkDescription?: string;
  errorSessionMismatchDescription?: string;

  // Buttons
  buttonRetry?: string;
  buttonClose?: string;
  buttonConnect?: string;
  buttonBack?: string;

  // Sources list (available apps)
  sourcesListHeading?: string;
  sourcesListLoading?: string;
  sourcesListEmpty?: string;

  // Footer
  poweredBy?: string;

  // Source config view - connection name
  configureNameLabel?: string;
  configureNameDescription?: string;
  configureNamePlaceholder?: string; // Use {source} placeholder

  // Source config view - sections
  configureAuthSection?: string;
  configureConfigSection?: string;

  // Source config view - buttons and status
  buttonCreateConnection?: string;
  buttonCreatingConnection?: string;
  connectionFailed?: string;
  loadSourceDetailsFailed?: string;
  fieldRequired?: string;
  fieldOptional?: string;

  // Auth method selector
  authMethodLabel?: string;
  authMethodDirect?: string;
  authMethodDirectDescription?: string;
  authMethodOAuth?: string; // Use {source} placeholder
  authMethodOAuthDescription?: string;

  // OAuth status UI
  oauthWaiting?: string;
  oauthWaitingDescription?: string;
  oauthPopupBlocked?: string;
  oauthPopupBlockedDescription?: string;
  buttonTryAgain?: string;
  buttonOpenLinkManually?: string;
  buttonConnectOAuth?: string; // Use {source} placeholder
  buttonConnecting?: string;

  // BYOC fields
  byocDescription?: string;
  byocClientIdLabel?: string;
  byocClientIdPlaceholder?: string;
  byocClientSecretLabel?: string;
  byocClientSecretPlaceholder?: string;

  // Empty state info
  welcomeInfoVerify?: string;
  welcomeInfoAccess?: string;

  // Folder selection
  folderSelectionHeading?: string;
  folderSelectionStartSync?: string;
  folderSelectionCount?: string; // Use {count} placeholder
}

export interface ConnectOptions {
  showConnectionName?: boolean; // default: false
  enableFolderSelection?: boolean; // default: false
  logoUrl?: string; // Logo URL for empty state
}

export interface ConnectTheme {
  mode: ThemeMode;
  colors?: {
    dark?: ThemeColors;
    light?: ThemeColors;
  };
  fonts?: ThemeFonts;
  labels?: ConnectLabels;
  options?: ConnectOptions;
}
