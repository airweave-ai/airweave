import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { useNavigate, useParams } from "react-router-dom";
import { apiClient } from "@/lib/api";
import { getAppIconUrl } from "@/lib/utils/icons";
import { useTheme } from "@/lib/theme-provider";

interface ISource {
  id: string;
  short_name: string;
  name: string;
}

interface ValidationError {
  errors: Array<Record<string, string>>;
}

interface WhiteLabelResponse {
  id: string;
  name: string;
  source_id: string;
  source_short_name: string;
  redirect_url: string;
  client_id: string;
}

interface WhiteLabelFormProps {
  onSuccess?: (data: WhiteLabelResponse) => void;
}

interface WhiteLabelFormData {
  name: string;
  source_short_name: string;
  redirect_url: string;
  client_id: string;
  client_secret: string;
}

// The shape we want for our create/update form
const formSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  source_short_name: z.string().min(1, "Please select a source"),
  redirect_url: z.string().url("Must be a valid URL"),
  client_id: z.string().min(1, "Client ID is required"),
  client_secret: z.string().min(1, "Client Secret is required"),
});

export function WhiteLabelForm({ onSuccess }: WhiteLabelFormProps) {
  const { whiteLabelId } = useParams();
  const navigate = useNavigate();
  const form = useForm<WhiteLabelFormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: "",
      source_short_name: "",
      redirect_url: "",
      client_id: "",
      client_secret: "",
    },
  });

  const [loading, setLoading] = useState(false);
  const [sources, setSources] = useState<ISource[]>([]);
  const [error, setError] = useState<string | null>(null);
  const { resolvedTheme } = useTheme();

  // Fetch available sources for the dropdown
  useEffect(() => {
    async function fetchSources() {
      try {
        const response = await apiClient.get("/sources/list");

        if (!response.ok) {
          throw new Error(`Failed to load data sources. Status: ${response.status}`);
        }
        const data = await response.json();
        // Sort sources alphabetically by name
        const sortedData = [...data].sort((a, b) => a.name.localeCompare(b.name));
        setSources(sortedData);
      } catch (err: any) {
        setError(err.message);
      }
    }
    fetchSources();
  }, []);

  // If editing an existing WhiteLabel, fetch it
  useEffect(() => {
    if (!whiteLabelId) return;
    async function fetchWhiteLabel() {
      setLoading(true);
      setError(null);
      try {
        const response = await apiClient.get(`/white_labels/${whiteLabelId}`);
        if (!response.ok) {
          throw new Error(`Failed to fetch white label. Status: ${response.status}`);
        }
        const data = await response.json();
        form.reset({
          name: data.name,
          source_short_name: data.source_short_name,
          redirect_url: data.redirect_url,
          client_id: data.client_id,
          client_secret: data.client_secret,
        });
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchWhiteLabel();
  }, [whiteLabelId, form]);

  const onSubmit = async (values: WhiteLabelFormData) => {
    setLoading(true);
    setError(null);
    try {
      const method = whiteLabelId ? "PUT" : "POST";
      const url = whiteLabelId
        ? `/white_labels/${whiteLabelId}`
        : "/white_labels";

      const response = await apiClient.post(url, values);

      if (!response.ok) {
        // Handle validation errors from backend
        if (response.status === 422) {
          const data = (await response.json()) as ValidationError;
          // Convert backend validation format to form errors
          const formErrors: Record<string, string> = {};
          data.errors.forEach((error) => {
            const [field, message] = Object.entries(error)[0];
            // Remove 'body.' prefix from field name
            const formField = field.replace('body.', '');
            formErrors[formField] = message;
          });

          // Set form errors
          Object.entries(formErrors).forEach(([field, message]) => {
            form.setError(field as keyof WhiteLabelFormData, {
              message,
            });
          });
          return;
        }

        throw new Error(
          `Failed to ${whiteLabelId ? "update" : "create"} white label. Status: ${
            response.status
          }`
        );
      }

      const data: WhiteLabelResponse = await response.json();

      if (whiteLabelId) {
        navigate("/white-label");
      } else {
        // Instead of navigating, emit the created data
        onSuccess?.(data);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!whiteLabelId) return;
    if (!confirm("Are you sure you want to delete this integration?")) return;

    try {
      setLoading(true);
      const response = await apiClient.delete(`/white_labels/${whiteLabelId}`);
      if (!response.ok) {
        throw new Error(`Failed to delete white label. Status: ${response.status}`);
      }
      navigate("/white-label");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">
        {whiteLabelId ? "Edit White Label" : "Create White Label"}
      </h2>

      {error && <p className="text-red-500">{error}</p>}

      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Integration Name</FormLabel>
                <FormControl>
                  <Input placeholder="My Integration" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="source_short_name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Data Source</FormLabel>
                <FormControl>
                  <Select
                    onValueChange={field.onChange}
                    value={field.value}
                  >
                    <SelectTrigger>
                      {field.value ? (
                        <div className="flex items-center gap-2">
                          <div className="w-5 h-5 shrink-0 flex items-center justify-center">
                            <img
                              src={getAppIconUrl(field.value, resolvedTheme)}
                              alt={field.value}
                              className="h-6 w-6"
                            />
                          </div>
                          {sources.find(s => s.short_name === field.value)?.name}
                        </div>
                      ) : (
                        <SelectValue placeholder="Select a data source" />
                      )}
                    </SelectTrigger>
                    <SelectContent>
                      {sources.map((src) => (
                        <SelectItem
                          key={src.short_name}
                          value={src.short_name}
                          className="flex items-center gap-2"
                        >
                          <div className="flex items-center gap-2">
                            <div className="w-5 h-5 shrink-0 flex items-center justify-center">
                              <img
                                src={getAppIconUrl(src.short_name, resolvedTheme)}
                                alt={src.short_name}
                                className="h-6 w-6"
                              />
                            </div>
                            {src.name}
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="redirect_url"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Frontend Callback URL</FormLabel>
                <FormControl>
                  <Input
                    placeholder="https://your-app.com/oauth/callback"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="client_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Client ID</FormLabel>
                <FormControl>
                  <Input placeholder="Your OAuth2 Client ID" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="client_secret"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Client Secret</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    placeholder="Your OAuth2 Client Secret"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="flex items-center gap-4">
            <Button type="submit" disabled={loading}>
              {whiteLabelId ? "Update" : "Create"}
            </Button>

            {whiteLabelId && (
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={loading}
              >
                Delete
              </Button>
            )}
          </div>
        </form>
      </Form>
    </div>
  );
}
