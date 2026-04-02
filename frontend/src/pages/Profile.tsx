import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { toast } from "sonner";
import { ActiveSessions } from "@/components/sessions/ActiveSessions";
import authConfig from "@/config/auth";

const Profile = () => {
  const navigate = useNavigate();
  const userEmail = localStorage.getItem("user") || "demo@example.com";

  const handleLogout = () => {
    localStorage.removeItem("user");
    toast.success("Successfully logged out");
    navigate("/login");
  };

  const handleSave = () => {
    toast.success("Profile updated successfully");
  };

  return (
    <div className="container pb-8">
      <h1 className="text-3xl font-bold mb-8">Profile</h1>

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <div className="flex items-center space-x-4">
              <Avatar className="h-16 w-16">
                <AvatarImage src="https://github.com/shadcn.png" />
                <AvatarFallback>JD</AvatarFallback>
              </Avatar>
              <div>
                <CardTitle>Demo User</CardTitle>
                <CardDescription>{userEmail}</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="first-name">First Name</Label>
                <Input id="first-name" defaultValue="Demo" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last-name">Last Name</Label>
                <Input id="last-name" defaultValue="User" />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" defaultValue={userEmail} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="company">Company</Label>
              <Input id="company" defaultValue="Demo Company" />
            </div>
            <div className="flex justify-between">
              <Button variant="destructive" onClick={handleLogout}>
                Logout
              </Button>
              <Button onClick={handleSave}>Save Changes</Button>
            </div>
          </CardContent>
        </Card>

        {authConfig.authEnabled && <ActiveSessions />}
      </div>
    </div>
  );
};

export default Profile;
