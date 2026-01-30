import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { OAuthConsentScreen } from '@/components/oauth/OAuthConsentScreen';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api-client';

export const OAuthConsentPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [collections, setCollections] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isFetchingCollections, setIsFetchingCollections] = useState(true);

  // Extract OAuth parameters from URL
  const clientId = searchParams.get('client_id');
  const redirectUri = searchParams.get('redirect_uri');
  const scope = searchParams.get('scope') || 'read:collection';
  const state = searchParams.get('state');
  const codeChallenge = searchParams.get('code_challenge');
  const codeChallengeMethod = searchParams.get('code_challenge_method');

  // Fetch user's collections
  useEffect(() => {
    const fetchCollections = async () => {
      try {
        const response = await apiClient.get('/collections');
        setCollections(response.data.collections || []);
      } catch (error) {
        console.error('Failed to fetch collections:', error);
        toast({
          title: 'Error',
          description: 'Failed to load collections. Please try again.',
          variant: 'destructive',
        });
      } finally {
        setIsFetchingCollections(false);
      }
    };

    fetchCollections();
  }, [toast]);

  // Validate required parameters
  useEffect(() => {
    if (!clientId || !redirectUri || !state) {
      toast({
        title: 'Invalid Request',
        description: 'Missing required OAuth parameters.',
        variant: 'destructive',
      });
      // Redirect to home after a delay
      setTimeout(() => navigate('/'), 3000);
    }
  }, [clientId, redirectUri, state, navigate, toast]);

  const handleApprove = async (collectionId: string) => {
    setIsLoading(true);

    try {
      // Create form data for OAuth authorization
      const formData = new FormData();
      formData.append('approved', 'true');
      formData.append('collection_id', collectionId);
      formData.append('client_id', clientId!);
      formData.append('redirect_uri', redirectUri!);
      formData.append('state', state!);
      formData.append('scope', scope);
      if (codeChallenge) {
        formData.append('code_challenge', codeChallenge);
        formData.append('code_challenge_method', codeChallengeMethod || 'S256');
      }

      // Submit authorization approval
      const response = await apiClient.post('/oauth/authorize', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Backend will return a redirect response
      // Follow the redirect (should include authorization code)
      if (response.status === 302 && response.headers.location) {
        window.location.href = response.headers.location;
      } else {
        // If not a redirect, something went wrong
        toast({
          title: 'Authorization Error',
          description: 'Failed to complete authorization. Please try again.',
          variant: 'destructive',
        });
      }
    } catch (error: any) {
      console.error('Authorization error:', error);
      toast({
        title: 'Authorization Failed',
        description: error.response?.data?.detail || 'An error occurred during authorization.',
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeny = () => {
    // Redirect back to client with access_denied error
    const errorUrl = `${redirectUri}?error=access_denied&state=${state}`;
    window.location.href = errorUrl;
  };

  if (isFetchingCollections) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Loading...</p>
      </div>
    );
  }

  if (!clientId || !redirectUri || !state) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p>Invalid OAuth request. Redirecting...</p>
      </div>
    );
  }

  // Get client name from client_id (you could also fetch this from an API)
  const getClientName = (id: string): string => {
    const clientNames: Record<string, string> = {
      'claude-desktop': 'Claude Desktop',
      'cursor': 'Cursor',
      'mcp-client': 'MCP Client',
    };
    return clientNames[id] || id;
  };

  return (
    <OAuthConsentScreen
      clientName={getClientName(clientId)}
      requestedScopes={scope.split(' ')}
      collections={collections}
      onApprove={handleApprove}
      onDeny={handleDeny}
      isLoading={isLoading}
    />
  );
};
