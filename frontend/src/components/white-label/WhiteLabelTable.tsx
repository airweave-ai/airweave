import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Eye } from "lucide-react";
import { apiClient } from "@/lib/api";

// Match whatever actual shape your backend returns for a WhiteLabel
interface WhiteLabel {
  id: string;
  name: string;
  redirect_url: string;
  created_at?: string;
  // ...any other props from your WhiteLabel model
}

export const WhiteLabelTable = () => {
  const navigate = useNavigate();
  const [whiteLabels, setWhiteLabels] = useState<WhiteLabel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchWhiteLabels() {
    try {
      setLoading(true);
      const response = await apiClient.get("/white_labels/list");
      if (!response.ok) {
        throw new Error(`Failed to load white labels. Status: ${response.status}`);
      }
      const data = await response.json();
      setWhiteLabels(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchWhiteLabels();
  }, []);

  if (loading) return <p className="p-2">Loading...</p>;
  if (error) return <p className="p-2 text-red-500">Error: {error}</p>;

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Integration ID</TableHead>
          <TableHead>Redirect URL</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Actions</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {whiteLabels.map((whiteLabel) => (
          <TableRow
            key={whiteLabel.id}
            className="cursor-pointer hover:bg-muted/50"
            onClick={() => navigate(`/white-label/${whiteLabel.id}`)}
          >
            <TableCell className="font-medium">{whiteLabel.name}</TableCell>
            <TableCell>{whiteLabel.id}</TableCell>
            <TableCell>{whiteLabel.redirect_url}</TableCell>
            <TableCell>
              {whiteLabel.created_at
                ? new Date(whiteLabel.created_at).toLocaleDateString()
                : "N/A"}
            </TableCell>
            <TableCell>
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  navigate(`/white-label/${whiteLabel.id}`);
                }}
              >
                <Eye className="h-4 w-4" />
              </Button>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
};
