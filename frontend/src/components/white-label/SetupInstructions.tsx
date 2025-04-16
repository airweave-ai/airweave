import { DataSource } from "@/config/dataSources";

interface SetupInstructionsProps {
  selectedSourceData: DataSource | undefined;
}

export const SetupInstructions = ({ selectedSourceData }: SetupInstructionsProps) => {
  if (!selectedSourceData) return null;

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">2. Configure Integration</h2>
      <div className="bg-secondary/10 p-4 rounded-lg space-y-2">
        <h3 className="font-medium">Setup Instructions for {selectedSourceData.name}</h3>
        <ol className="list-decimal list-inside space-y-2 text-sm">
          <li>Go to your {selectedSourceData.name} Developer Console</li>
          <li>Create a new OAuth2 application</li>
          <li>Set the callback URL to your frontend URL</li>
          <li>Copy the Client ID and Client Secret</li>
          <li>Fill out the form below with your application details</li>
        </ol>
      </div>
    </div>
  );
};
