import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Bell } from "lucide-react";

export function NotificationSettings() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Bell className="h-5 w-5 text-primary" />
          <CardTitle>Notifications</CardTitle>
        </div>
        <CardDescription>
          Configure how you want to receive notifications
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Email Notifications</Label>
            <div className="text-sm text-muted-foreground">
              Receive notifications about sync status
            </div>
          </div>
          <Switch defaultChecked />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Slack Notifications</Label>
            <div className="text-sm text-muted-foreground">
              Send notifications to Slack
            </div>
          </div>
          <Switch />
        </div>

        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <Label>Discord Notifications</Label>
            <div className="text-sm text-muted-foreground">
              Send notifications to Discord
            </div>
          </div>
          <Switch />
        </div>
      </CardContent>
    </Card>
  );
}
