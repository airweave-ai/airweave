/**
 * Tests for OAuthConsentScreen component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { OAuthConsentScreen } from '../OAuthConsentScreen';

describe('OAuthConsentScreen', () => {
  const mockCollections = [
    { id: 'col-1', name: 'My Linear Issues', readable_id: 'linear-issues' },
    { id: 'col-2', name: 'GitHub Repos', readable_id: 'github-repos' },
    { id: 'col-3', name: 'Slack Messages', readable_id: 'slack-messages' },
  ];

  const mockOnApprove = vi.fn();
  const mockOnDeny = vi.fn();

  const defaultProps = {
    clientName: 'Claude Desktop',
    requestedScopes: ['read:collection'],
    collections: mockCollections,
    onApprove: mockOnApprove,
    onDeny: mockOnDeny,
    isLoading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders client information correctly', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    expect(screen.getByText(/Authorize Claude Desktop/i)).toBeInTheDocument();
    expect(screen.getByText(/Claude Desktop wants to access your Airweave data/i)).toBeInTheDocument();
  });

  it('displays requested scopes with descriptions', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    expect(screen.getByText(/Search and read data from your collection/i)).toBeInTheDocument();
  });

  it('displays collection dropdown with user collections', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    const selectTrigger = screen.getByRole('combobox');
    expect(selectTrigger).toBeInTheDocument();

    // Open dropdown
    fireEvent.click(selectTrigger);

    // Verify all collections are shown
    expect(screen.getByText('My Linear Issues')).toBeInTheDocument();
    expect(screen.getByText('GitHub Repos')).toBeInTheDocument();
    expect(screen.getByText('Slack Messages')).toBeInTheDocument();
  });

  it('auto-selects first collection when only one available', () => {
    const singleCollection = [mockCollections[0]];
    
    render(
      <OAuthConsentScreen
        {...defaultProps}
        collections={singleCollection}
      />
    );

    // Verify collection is auto-selected (Authorize button should be enabled)
    const authorizeButton = screen.getByRole('button', { name: /Authorize/i });
    expect(authorizeButton).not.toBeDisabled();
  });

  it('disables approve button when no collection selected', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    const authorizeButton = screen.getByRole('button', { name: /Authorize/i });
    
    // Should be disabled initially (no collection selected)
    expect(authorizeButton).toBeDisabled();
  });

  it('enables approve button after selecting collection', async () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    const authorizeButton = screen.getByRole('button', { name: /Authorize/i });
    expect(authorizeButton).toBeDisabled();

    // Select a collection
    const selectTrigger = screen.getByRole('combobox');
    fireEvent.click(selectTrigger);
    fireEvent.click(screen.getByText('My Linear Issues'));

    await waitFor(() => {
      expect(authorizeButton).not.toBeDisabled();
    });
  });

  it('calls onApprove with selected collection ID when user approves', async () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    // Select collection
    const selectTrigger = screen.getByRole('combobox');
    fireEvent.click(selectTrigger);
    fireEvent.click(screen.getByText('GitHub Repos'));

    // Click approve
    const authorizeButton = screen.getByRole('button', { name: /Authorize/i });
    fireEvent.click(authorizeButton);

    await waitFor(() => {
      expect(mockOnApprove).toHaveBeenCalledWith('col-2');
    });
  });

  it('calls onDeny when user denies', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    const denyButton = screen.getByRole('button', { name: /Deny/i });
    fireEvent.click(denyButton);

    expect(mockOnDeny).toHaveBeenCalled();
  });

  it('shows loading state correctly', () => {
    render(<OAuthConsentScreen {...defaultProps} isLoading={true} />);

    expect(screen.getByText(/Authorizing.../i)).toBeInTheDocument();
    
    const authorizeButton = screen.getByRole('button', { name: /Authorizing.../i });
    expect(authorizeButton).toBeDisabled();
    
    const denyButton = screen.getByRole('button', { name: /Deny/i });
    expect(denyButton).toBeDisabled();
  });

  it('displays security warning', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    expect(screen.getByText(/Only authorize applications you trust/i)).toBeInTheDocument();
    expect(screen.getByText(/You can revoke access at any time/i)).toBeInTheDocument();
  });

  it('shows scope limitation notice', () => {
    render(<OAuthConsentScreen {...defaultProps} />);

    expect(screen.getByText(/will only have access to this collection/i)).toBeInTheDocument();
  });

  it('renders multiple scopes correctly', () => {
    const multiScopeProps = {
      ...defaultProps,
      requestedScopes: ['read:collection', 'write:collection'],
    };

    render(<OAuthConsentScreen {...multiScopeProps} />);

    expect(screen.getByText(/Search and read data from your collection/i)).toBeInTheDocument();
    expect(screen.getByText(/Add or modify data in your collection/i)).toBeInTheDocument();
  });
});
