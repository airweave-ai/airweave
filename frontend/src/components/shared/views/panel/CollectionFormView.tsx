import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Loader2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useSidePanelStore } from "@/lib/stores/sidePanelStore";
import { useCollectionsStore } from "@/lib/stores/collections";
import { toast } from "sonner";

const formSchema = z.object({
    name: z.string().min(4, "Name must be at least 4 characters").max(64, "Name must be less than 64 characters"),
    description: z.string().optional(),
});

export const CollectionFormView = () => {
    const navigate = useNavigate();
    const { setView } = useSidePanelStore.getState();
    const { fetchCollections } = useCollectionsStore.getState();
    const [isSubmitting, setIsSubmitting] = useState(false);

    const form = useForm<z.infer<typeof formSchema>>({
        resolver: zodResolver(formSchema),
        defaultValues: { name: "", description: "" },
    });

    const onSubmit = async (values: z.infer<typeof formSchema>) => {
        setIsSubmitting(true);
        try {
            const response = await apiClient.post("/collections/", values);

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Failed to create collection");
            }

            const newCollection = await response.json();
            toast.success(`Collection "${newCollection.name}" created!`);

            // Force a refresh of the collections list in the sidebar
            await fetchCollections(true);

            // Navigate to the new collection page
            navigate(`/collections/${newCollection.readable_id}`);

            // IMPORTANT: Transition the panel to the next step
            setView('sourceList', {
                collectionId: newCollection.readable_id,
                collectionName: newCollection.name
            });

        } catch (error) {
            console.error("Error creating collection:", error);
            toast.error(error instanceof Error ? error.message : "An unknown error occurred.");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="p-6">
            <Form {...form}>
                <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                    <FormField
                        control={form.control}
                        name="name"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Collection Name</FormLabel>
                                <FormControl>
                                    <Input placeholder="e.g., Customer Support Tickets" {...field} />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <FormField
                        control={form.control}
                        name="description"
                        render={({ field }) => (
                            <FormItem>
                                <FormLabel>Description (Optional)</FormLabel>
                                <FormControl>
                                    <Textarea
                                        placeholder="Describe what this collection is for..."
                                        className="resize-none"
                                        {...field}
                                    />
                                </FormControl>
                                <FormMessage />
                            </FormItem>
                        )}
                    />
                    <div className="flex justify-end">
                        <Button type="submit" disabled={isSubmitting}>
                            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Create and Add Source
                        </Button>
                    </div>
                </form>
            </Form>
        </div>
    );
};
