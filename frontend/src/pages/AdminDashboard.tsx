import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/auth-context';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Shield, Building2, Activity } from 'lucide-react';
import { toast } from 'sonner';
import { OrganizationsTab } from './admin/OrganizationsTab';
import { SyncsTab } from './admin/SyncsTab';

export function AdminDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Redirect if not admin
    if (user && !user.is_admin) {
      toast.error('Admin access required');
      navigate('/');
      return;
    }
  }, [user, navigate]);

  if (!user?.is_admin) {
    return null;
  }

  return (
    <div className="container mx-auto py-6 px-4 max-w-[1800px]">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-3xl font-bold">Admin Dashboard</h1>
            <p className="text-muted-foreground">Manage organizations and syncs across the platform</p>
          </div>
        </div>
      </div>

      <Tabs defaultValue="organizations" className="w-full">
        <TabsList className="mb-6">
          <TabsTrigger value="organizations" className="gap-2">
            <Building2 className="h-4 w-4" />
            Organizations
          </TabsTrigger>
          <TabsTrigger value="syncs" className="gap-2">
            <Activity className="h-4 w-4" />
            Syncs
          </TabsTrigger>
        </TabsList>

        <TabsContent value="organizations" className="mt-0">
          <OrganizationsTab />
        </TabsContent>

        <TabsContent value="syncs" className="mt-0">
          <SyncsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
