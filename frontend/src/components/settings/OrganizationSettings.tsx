import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Building2, InfoIcon, Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface Organization {
  id: string;
  name: string;
  description?: string;
}

export function OrganizationSettings() {
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganization();
  }, []);

  const fetchOrganization = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get<Organization>("/users/me/organization");

      if (!response.ok) {
        throw new Error(`API request failed with status ${response.status}`);
      }

      const data = await response.json();
      setOrganization(data);
    } catch (err) {
      console.error("Failed to fetch organization:", err);
      setError(
        typeof err === 'object' && err !== null && 'message' in err
          ? String(err.message)
          : "Failed to load organization data. Please try again later."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="border-0 shadow-none bg-transparent">
        <CardHeader className="px-0 pt-0">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-primary" />
            <CardTitle>Organization Details</CardTitle>
          </div>
          <CardDescription>
            View your organization settings and information
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 px-0">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : organization ? (
            <>
              <div className="space-y-1">
                <Label htmlFor="organization-name">Organization Name</Label>
                <div className="flex items-center gap-2">
                  <Input
                    id="organization-name"
                    value={organization.name}
                    disabled
                    className="bg-muted"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="organization-id">Organization ID</Label>
                <div className="relative">
                  <Input
                    id="organization-id"
                    value={organization.id}
                    disabled
                    className="bg-muted font-mono text-xs pr-8"
                  />
                  <div className="absolute right-3 top-2.5 text-muted-foreground">
                    <InfoIcon className="h-4 w-4" />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Use this ID when referencing your organization in API calls
                </p>
              </div>

              {organization.description && (
                <div className="space-y-1">
                  <Label htmlFor="organization-description">Description</Label>
                  <Input
                    id="organization-description"
                    value={organization.description}
                    disabled
                    className="bg-muted"
                  />
                </div>
              )}

              <div className="rounded-md bg-muted p-4">
                <div className="flex gap-2">
                  <InfoIcon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-medium">Organization Settings</h4>
                    <p className="text-sm text-muted-foreground">
                      Additional organization settings will be available in a future update.
                    </p>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-6 text-muted-foreground">
              No organization data found
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
