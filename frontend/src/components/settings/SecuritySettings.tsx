import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Shield } from "lucide-react";

export function SecuritySettings() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Shield className="h-5 w-5 text-primary" />
          <CardTitle>Security</CardTitle>
        </div>
        <CardDescription>
          Configure security and access control settings
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>IP Whitelisting</Label>
            <div className="text-sm text-muted-foreground">
              Restrict access to specific IPs
            </div>
          </div>
          <Switch />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Rate Limiting</Label>
            <div className="text-sm text-muted-foreground">
              Enable API rate limiting
            </div>
          </div>
          <Switch defaultChecked />
        </div>

        <div className="space-y-2">
          <Label>Authentication Method</Label>
          <Select defaultValue="jwt">
            <SelectTrigger>
              <SelectValue placeholder="Select auth method" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="jwt">JWT</SelectItem>
              <SelectItem value="apikey">API Key</SelectItem>
              <SelectItem value="oauth">OAuth 2.0</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </CardContent>
    </Card>
  );
}
