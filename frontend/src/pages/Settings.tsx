import { Settings2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OrganizationSettings } from "@/components/settings/OrganizationSettings";
import { AppearanceSettings } from "@/components/settings/AppearanceSettings";
import { APIKeysSettings } from "@/components/settings/APIKeysSettings";

const Settings = () => {
  return (
    <div className="container pb-8">
      <div className="flex items-center gap-2 mb-8">
        <Settings2 className="h-8 w-8 text-primary" />
        <h1 className="text-3xl font-bold">Settings</h1>
      </div>

      <Tabs defaultValue="organization" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 lg:w-[400px]">
          <TabsTrigger value="organization">Organization</TabsTrigger>
          <TabsTrigger value="appearance">Appearance</TabsTrigger>
          <TabsTrigger value="apikeys">API Keys</TabsTrigger>
        </TabsList>

        <div className="max-w-4xl">
          <TabsContent value="organization" className="mt-6">
            <OrganizationSettings />
          </TabsContent>

          <TabsContent value="appearance" className="mt-6">
            <AppearanceSettings />
          </TabsContent>

          <TabsContent value="apikeys" className="mt-6">
            <APIKeysSettings />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
};

export default Settings;
