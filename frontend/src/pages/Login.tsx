import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "sonner";

const Login = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  // Check for stored user on component mount
  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      setEmail(storedUser);
      navigate("/dashboard");
    }
  }, [navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      // Store email in localStorage
      localStorage.setItem("user", email);

      // Submit to Mailchimp
      const formData = new FormData();
      formData.append('EMAIL', email);
      formData.append('u', 'd1208c7c2557a0ebae2bf326e');
      formData.append('id', '211fc57393');

      await fetch(
        'https://neena.us14.list-manage.com/subscribe/post?u=d1208c7c2557a0ebae2bf326e&id=211fc57393',
        {
          method: 'POST',
          mode: 'no-cors',
          body: formData
        }
      );

      toast.success("Successfully logged in!");
      navigate("/dashboard");
    } catch (error) {
      // Even if Mailchimp fails, we still want to log the user in
      console.error('Mailchimp subscription error:', error);
      toast.success("Successfully logged in!");
      navigate("/dashboard");
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-2 text-center">
          <CardTitle className="text-3xl font-bold">
            Welcome to{" "}
            <span className="bg-gradient-to-r from-primary-400 to-secondary-400 bg-clip-text text-transparent">
              Airweave
            </span>
          </CardTitle>
          <CardDescription>
            Enter any email to try out the demo
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Input
                type="email"
                placeholder="Enter your email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full">
              Start Using Airweave
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="mt-8 text-sm text-muted-foreground">
        <div className="flex gap-4 justify-center">
          <a
            href="/privacy"
            className="hover:text-primary transition-colors"
          >
            Privacy Policy
          </a>
          <span>•</span>
          <a
            href="/terms"
            className="hover:text-primary transition-colors"
          >
            Terms of Use
          </a>
        </div>
      </div>
    </div>
  );
};

export default Login;
