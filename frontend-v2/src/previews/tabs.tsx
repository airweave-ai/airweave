import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../components/ui/tabs";
import type { ComponentPreviewConfig } from "./types";

export const tabsPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "Basic tabs with content panels",
      preview: (
        <Tabs defaultValue="account" className="w-[400px]">
          <TabsList>
            <TabsTrigger value="account">Account</TabsTrigger>
            <TabsTrigger value="password">Password</TabsTrigger>
          </TabsList>
          <TabsContent value="account">
            <Card>
              <CardHeader>
                <CardTitle>Account</CardTitle>
                <CardDescription>
                  Make changes to your account here. Click save when you're
                  done.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="space-y-1">
                  <label htmlFor="name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input id="name" defaultValue="John Doe" />
                </div>
                <div className="space-y-1">
                  <label htmlFor="username" className="text-sm font-medium">
                    Username
                  </label>
                  <Input id="username" defaultValue="@johndoe" />
                </div>
              </CardContent>
              <CardFooter>
                <Button>Save changes</Button>
              </CardFooter>
            </Card>
          </TabsContent>
          <TabsContent value="password">
            <Card>
              <CardHeader>
                <CardTitle>Password</CardTitle>
                <CardDescription>
                  Change your password here. After saving, you'll be logged out.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="space-y-1">
                  <label htmlFor="current" className="text-sm font-medium">
                    Current password
                  </label>
                  <Input id="current" type="password" />
                </div>
                <div className="space-y-1">
                  <label htmlFor="new" className="text-sm font-medium">
                    New password
                  </label>
                  <Input id="new" type="password" />
                </div>
              </CardContent>
              <CardFooter>
                <Button>Save password</Button>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>
      ),
      code: `<Tabs defaultValue="account" className="w-[400px]">
  <TabsList>
    <TabsTrigger value="account">Account</TabsTrigger>
    <TabsTrigger value="password">Password</TabsTrigger>
  </TabsList>
  <TabsContent value="account">
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
        <CardDescription>Make changes to your account here.</CardDescription>
      </CardHeader>
      <CardContent>
        {/* Form fields */}
      </CardContent>
      <CardFooter>
        <Button>Save changes</Button>
      </CardFooter>
    </Card>
  </TabsContent>
  <TabsContent value="password">
    {/* Password tab content */}
  </TabsContent>
</Tabs>`,
    },
    {
      title: "Simple Tabs",
      description: "Tabs with simple text content",
      preview: (
        <Tabs defaultValue="overview" className="w-[400px]">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="reports">Reports</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="p-4">
            <p className="text-muted-foreground text-sm">
              Your overview content goes here. This tab shows a summary of your
              data.
            </p>
          </TabsContent>
          <TabsContent value="analytics" className="p-4">
            <p className="text-muted-foreground text-sm">
              Analytics content with charts and metrics would appear here.
            </p>
          </TabsContent>
          <TabsContent value="reports" className="p-4">
            <p className="text-muted-foreground text-sm">
              View and download your reports from this section.
            </p>
          </TabsContent>
        </Tabs>
      ),
      code: `<Tabs defaultValue="overview">
  <TabsList className="grid w-full grid-cols-3">
    <TabsTrigger value="overview">Overview</TabsTrigger>
    <TabsTrigger value="analytics">Analytics</TabsTrigger>
    <TabsTrigger value="reports">Reports</TabsTrigger>
  </TabsList>
  <TabsContent value="overview">
    <p>Overview content</p>
  </TabsContent>
  <TabsContent value="analytics">
    <p>Analytics content</p>
  </TabsContent>
  <TabsContent value="reports">
    <p>Reports content</p>
  </TabsContent>
</Tabs>`,
    },
  ],
};
