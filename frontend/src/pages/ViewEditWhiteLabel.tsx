import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Eye, EyeOff, ArrowLeft, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { apiClient } from "@/lib/api";
import { CodeSnippet } from "@/components/white-label/CodeSnippet";
import { TestIntegrationCard } from "@/components/white-label/TestIntegrationCard";

interface Sync {
  id: string;
  name: string;
  description: string;
  status: string;
  schedule: string;
  white_label_id: string;
  source_id: string;
  destination_id: string;
  created_at: string;
  modified_at: string;
  created_by_email: string;
  modified_by_email: string;
  last_run_at?: string;
  next_run_at?: string;
}

interface WhiteLabel {
  id: string;
  name: string;
  source_id: string;
  source_short_name: string;
  redirect_url: string;
  client_id: string;
  client_secret: string;
  organization_id: string;
  created_at: string;
  modified_at: string;
  created_by_email: string;
  modified_by_email: string;
}

const ViewEditWhiteLabel = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [showSecret, setShowSecret] = useState(false);
  const [showDeleteAlert, setShowDeleteAlert] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [whiteLabel, setWhiteLabel] = useState<WhiteLabel | null>(null);
  const [syncs, setSyncs] = useState<Sync[]>([]);
  const [isSyncsLoading, setIsSyncsLoading] = useState(true);

  useEffect(() => {
    const fetchWhiteLabel = async () => {
      try {
        const response = await apiClient.get(`/white_labels/${id}`);
        if (!response.ok) {
          throw new Error('Failed to fetch white label details');
        }
        const data = await response.json();
        setWhiteLabel(data);
      } catch (error) {
        toast.error('Failed to load white label details');
        console.error(error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchWhiteLabel();
  }, [id]);

  useEffect(() => {
    const fetchSyncs = async () => {
      try {
        const response = await apiClient.get(`/white_labels/${id}/syncs`);
        if (!response.ok) {
          throw new Error('Failed to fetch syncs');
        }
        const data = await response.json();
        setSyncs(data);
      } catch (error) {
        toast.error('Failed to load syncs');
        console.error(error);
      } finally {
        setIsSyncsLoading(false);
      }
    };

    if (id) {
      fetchSyncs();
    }
  }, [id]);

  const handleDelete = async () => {
    try {
      const response = await apiClient.delete(`/white_labels/${id}`);
      if (!response.ok) {
        throw new Error('Failed to delete white label');
      }
      toast.success("Integration deleted successfully");
      navigate("/white-label");
    } catch (error) {
      toast.error('Failed to delete white label');
      console.error(error);
    }
  };

  const handleSave = async (formData: Partial<WhiteLabel>) => {
    try {
      const response = await apiClient.put(`/white_labels/${id}`, {
        body: JSON.stringify({
          name: formData.name,
          redirect_url: formData.redirect_url,
          client_id: formData.client_id,
          client_secret: formData.client_secret,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update white label');
      }

      const updatedData = await response.json();
      setWhiteLabel(updatedData);
      toast.success("Changes saved successfully");
    } catch (error) {
      toast.error('Failed to save changes');
      console.error(error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  if (!whiteLabel) {
    return (
      <div className="container mx-auto pb-8">
        <div className="text-center text-muted-foreground">
          White label not found
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto pb-8 space-y-8">
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/white-label")}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Edit White Label</h1>
          <p className="text-muted-foreground mt-2">
            Manage your OAuth2 integration settings
          </p>
        </div>
      </div>

      <Card className="p-6 space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="name">White Label Name</Label>
            <Input
              id="name"
              defaultValue={whiteLabel.name}
              onChange={(e) => handleSave({ ...whiteLabel, name: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="clientId">Client ID</Label>
            <Input
              id="clientId"
              defaultValue={whiteLabel.client_id}
              onChange={(e) => handleSave({ ...whiteLabel, client_id: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="clientSecret">Client Secret</Label>
            <div className="relative">
              <Input
                id="clientSecret"
                type={showSecret ? "text" : "password"}
                defaultValue={whiteLabel.client_secret}
                onChange={(e) => handleSave({ ...whiteLabel, client_secret: e.target.value })}
              />
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setShowSecret(!showSecret)}
              >
                {showSecret ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="redirectUrl">Frontend Callback URL</Label>
            <Input
              id="redirectUrl"
              defaultValue={whiteLabel.redirect_url}
              onChange={(e) => handleSave({ ...whiteLabel, redirect_url: e.target.value })}
            />
          </div>

          <div className="space-y-2">
            <Label>Created By</Label>
            <div className="text-sm text-muted-foreground">{whiteLabel.created_by_email}</div>
            <div className="text-xs text-muted-foreground">
              {new Date(whiteLabel.created_at).toLocaleString()}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Last Modified By</Label>
            <div className="text-sm text-muted-foreground">{whiteLabel.modified_by_email}</div>
            <div className="text-xs text-muted-foreground">
              {new Date(whiteLabel.modified_at).toLocaleString()}
            </div>
          </div>

          <div className="flex justify-between pt-4">
            <Button
              variant="destructive"
              onClick={() => setShowDeleteAlert(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Delete Integration
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Integration Code</CardTitle>
          <CardDescription>
            Copy these code snippets to implement the OAuth2 flow in your application.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <CodeSnippet
            whitelabelGuid={whiteLabel.id}
            frontendUrl={whiteLabel.redirect_url}
            clientId={whiteLabel.client_id}
            source={whiteLabel.source_short_name}
          />
        </CardContent>
      </Card>
      <TestIntegrationCard whitelabelId={whiteLabel.id} />
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Sync Pipelines</h2>
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last Sync</TableHead>
                <TableHead>Next Sync</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isSyncsLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center">
                    <div className="flex items-center justify-center py-4">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
                    </div>
                  </TableCell>
                </TableRow>
              ) : syncs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground py-4">
                    No syncs found
                  </TableCell>
                </TableRow>
              ) : (
                syncs.map((sync) => (
                  <TableRow
                    key={sync.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/sync/${sync.id}`)}
                  >
                    <TableCell>{sync.name}</TableCell>
                    <TableCell>
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          sync.status === "active"
                            ? "bg-green-100 text-green-800"
                            : "bg-yellow-100 text-yellow-800"
                        }`}
                      >
                        {sync.status}
                      </span>
                    </TableCell>
                    <TableCell>
                      {sync.last_run_at
                        ? new Date(sync.last_run_at).toLocaleString()
                        : 'Never'}
                    </TableCell>
                    <TableCell>
                      {sync.next_run_at
                        ? new Date(sync.next_run_at).toLocaleString()
                        : 'Not scheduled'}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </Card>
      </div>

      <AlertDialog open={showDeleteAlert} onOpenChange={setShowDeleteAlert}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>
              This action cannot be undone. This will permanently delete the
              integration and remove all associated sync pipelines.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default ViewEditWhiteLabel;
