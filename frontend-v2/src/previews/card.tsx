import { Button } from "../components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { Input } from "../components/ui/input";
import type { ComponentPreviewConfig } from "./types";

export const cardPreview: ComponentPreviewConfig = {
  variants: [
    {
      title: "Default",
      description: "A basic card with header, content, and footer",
      preview: (
        <Card className="w-[350px]">
          <CardHeader>
            <CardTitle>Card Title</CardTitle>
            <CardDescription>
              Card description goes here to provide context.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              This is the main content area of the card. You can put any content
              here including forms, text, images, and more.
            </p>
          </CardContent>
          <CardFooter>
            <Button className="w-full">Action</Button>
          </CardFooter>
        </Card>
      ),
      code: `<Card className="w-[350px]">
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardDescription>
      Card description goes here to provide context.
    </CardDescription>
  </CardHeader>
  <CardContent>
    <p>This is the main content area of the card.</p>
  </CardContent>
  <CardFooter>
    <Button className="w-full">Action</Button>
  </CardFooter>
</Card>`,
    },
    {
      title: "With Action",
      description: "Card header can include an action button",
      preview: (
        <Card className="w-[350px]">
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
            <CardDescription>You have 3 unread messages.</CardDescription>
            <CardAction>
              <Button variant="outline" size="sm">
                Mark all read
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="bg-muted rounded-md p-3 text-sm">
                New message from John
              </div>
              <div className="bg-muted rounded-md p-3 text-sm">
                Meeting reminder for tomorrow
              </div>
              <div className="bg-muted rounded-md p-3 text-sm">
                Your report is ready
              </div>
            </div>
          </CardContent>
        </Card>
      ),
      code: `<Card>
  <CardHeader>
    <CardTitle>Notifications</CardTitle>
    <CardDescription>You have 3 unread messages.</CardDescription>
    <CardAction>
      <Button variant="outline" size="sm">Mark all read</Button>
    </CardAction>
  </CardHeader>
  <CardContent>
    {/* Content */}
  </CardContent>
</Card>`,
    },
    {
      title: "Form Card",
      description: "Card containing a simple form",
      preview: (
        <Card className="w-[350px]">
          <CardHeader>
            <CardTitle>Create project</CardTitle>
            <CardDescription>
              Deploy your new project in one-click.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form>
              <div className="grid w-full items-center gap-4">
                <div className="flex flex-col space-y-1.5">
                  <label htmlFor="name" className="text-sm font-medium">
                    Name
                  </label>
                  <Input id="name" placeholder="Name of your project" />
                </div>
              </div>
            </form>
          </CardContent>
          <CardFooter className="flex justify-between">
            <Button variant="outline">Cancel</Button>
            <Button>Deploy</Button>
          </CardFooter>
        </Card>
      ),
      code: `<Card className="w-[350px]">
  <CardHeader>
    <CardTitle>Create project</CardTitle>
    <CardDescription>Deploy your new project in one-click.</CardDescription>
  </CardHeader>
  <CardContent>
    <form>
      <div className="grid w-full items-center gap-4">
        <div className="flex flex-col space-y-1.5">
          <label htmlFor="name">Name</label>
          <Input id="name" placeholder="Name of your project" />
        </div>
      </div>
    </form>
  </CardContent>
  <CardFooter className="flex justify-between">
    <Button variant="outline">Cancel</Button>
    <Button>Deploy</Button>
  </CardFooter>
</Card>`,
    },
  ],
};
