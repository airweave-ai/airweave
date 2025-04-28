import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { Card } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { ChatSidebar } from "@/components/chat/ChatSidebar";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ChatInfoSidebar } from "@/components/chat/ChatInfoSidebar";
import { ChatInfo, ModelSettings } from "@/components/chat/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { API_CONFIG, apiClient } from "@/lib/api";
import ReactMarkdown from 'react-markdown';

import { CreateChatDialog } from "@/components/chat/CreateChatDialog";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useTheme } from "@/lib/theme-provider";


interface Chat {
  id: string;
  modified_at: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  attachments?: string[];
  id: number;
}

function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const { toast } = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const [chatInfo, setChatInfo] = useState<ChatInfo | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [isOpenAIKeySet, setIsOpenAIKeySet] = useState<boolean | null>(null);
  const { resolvedTheme } = useTheme();
  // If you're using a route param like /chat/:chatId
  const { id } = useParams<{ id: string }>();
  const chatId = useMemo(() => id, [id]); // Ensure stable reference

  // Add a new state to track if chat is ready for messages
  const [chatReady, setChatReady] = useState(false);

  // Add this right after the messages state declaration
  // Add console logs to help debug messages
  useEffect(() => {
    console.log("Current messages:", messages);
  }, [messages]);

  // Consolidate useEffects to reduce network calls on page refresh
  useEffect(() => {
    const checkOpenAIKeyAndInitChats = async () => {
      try {
        // Check OpenAI key first
        const keyResponse = await apiClient.get('/chat/openai_key_set');
        const isSet = await keyResponse.json();
        setIsOpenAIKeySet(isSet);

        if (!isSet) return;

        // Only continue if the key is set
        const response = await apiClient.get('/chat');
        const chats = await response.json();

        // Handle existing chats or create dialog logic
        if (chats && chats.length > 0) {
          // If we don't have a chatId, navigate to the most recent chat
          if (!chatId) {
            const mostRecentChat = chats.sort((a: Chat, b: Chat) =>
              new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
            )[0];
            navigate(`/chat/${mostRecentChat.id}`);
          }
        } else if (!chatId) {
          // Only show create dialog if there are no chats AND no chatId
          setShowCreateDialog(true);
        }

        setIsLoading(false);
      } catch (error) {
        console.error("Failed to initialize:", error);
        toast({
          title: "Error",
          description: "Failed to initialize chat. Please try again.",
          variant: "destructive",
        });
        setIsLoading(false);
      }
    };

    void checkOpenAIKeyAndInitChats();
  }, [chatId, navigate, toast]);

  // Single useEffect for loading chat data when chatId changes
  useEffect(() => {
    async function loadChatAndInfo() {
      if (!chatId) {
        console.log("No chat ID available, skipping data load");
        return;
      }

      try {
        setIsLoading(true);
        setChatReady(false); // Reset chat ready state during loading
        setError(null);

        console.log(`Loading chat data for ID: ${chatId}`);

        // Load chat messages
        const resp = await apiClient.get(`/chat/${chatId}`);
        if (!resp.ok) {
          throw new Error(`Failed to load chat: ${resp.statusText}`);
        }

        const chatData = await resp.json();
        console.log("Chat data from API:", chatData);

        // Set messages - make sure we're handling the API response format correctly
        const messagesFromAPI = chatData.messages || [];
        console.log("Raw messages from API:", messagesFromAPI);

        if (messagesFromAPI && Array.isArray(messagesFromAPI)) {
          const formattedMessages = messagesFromAPI.map((m: any, index: number) => ({
            role: m.role || 'user',
            content: m.content || '',
            attachments: m.attachments || [],
            id: m.id || Date.now() + index, // Ensure unique IDs
          }));

          console.log("Formatted messages:", formattedMessages);
          setMessages(formattedMessages);
        } else {
          console.error("Invalid messages format from API:", messagesFromAPI);
          setMessages([]);
        }

        // Load chat info in the same effect
        try {
          // Get sync info
          const syncResponse = await apiClient.get(`/sync/${chatData.sync_id}`);
          const syncData = await syncResponse.json();

          // Get source connection
          const sourceConnResponse = await apiClient.get(`/connections/detail/${syncData.source_connection_id}`);
          const sourceConnData = await sourceConnResponse.json();

          // Get source details
          const sourceResponse = await apiClient.get(`/sources/detail/${sourceConnData.short_name}`);
          const sourceData = await sourceResponse.json();

          // Get destination connection and details if exists
          let destinationConnData = null;
          let destinationData = null;

          if (syncData.destination_connection_id) {
            const destConnResponse = await apiClient.get(`/connections/detail/${syncData.destination_connection_id}`);
            destinationConnData = await destConnResponse.json();

            const destResponse = await apiClient.get(`/destinations/detail/${destinationConnData.short_name}`);
            destinationData = await destResponse.json();
          }

          // Combine all the data
          setChatInfo({
            ...chatData,
            sync: {
              ...syncData,
              source_connection: {
                ...sourceConnData,
                source: sourceData
              },
              destination_connection: destinationConnData ? {
                ...destinationConnData,
                destination: destinationData
              } : null
            }
          });

          // Set chat as ready after successful loading
          setChatReady(true);
        } catch (error) {
          console.error("Failed to load chat info:", error);
          // Continue even if chat info fails to load, but still mark as ready
          setChatReady(true);
        }

      } catch (error) {
        console.error("Failed to load chat:", error);
        setError(error.message || "Failed to load chat. Please try again.");
        toast({
          title: "Error",
          description: error.message || "Failed to load chat. Please try again.",
          variant: "destructive",
        });
        // Only navigate away if it's a 404
        if (error.response?.status === 404) {
          navigate("/");
        }
      } finally {
        setIsLoading(false);
      }
    }

    void loadChatAndInfo();
  }, [chatId, navigate, toast]);

  // Auto-run if user came here with an initial message or sources
  useEffect(() => {
    const state = location.state as { initialMessage?: string; selectedSources?: string[] };
    if (state?.selectedSources) {
      setSelectedSources(state.selectedSources);
    }
    if (state?.initialMessage) {
      void handleSubmit(state.initialMessage, []);
    }
  }, [location.state]);

  // Submit a message via SSE endpoint
  const handleSubmit = useCallback(
    async (content: string, attachments: string[]) => {
      // Make sure we have a chatId and the chat is ready before sending
      if (!chatId) {
        console.error("Chat ID is missing, can't send message");
        toast({
          title: "Error",
          description: "Unable to send message (no chat ID found)",
          variant: "destructive",
        });
        return;
      }

      if (!chatReady) {
        console.error("Chat not ready yet, can't send message");
        toast({
          title: "Error",
          description: "Please wait until chat is fully loaded",
          variant: "destructive",
        });
        return;
      }

      try {
        // Create a unique ID for the message
        const messageId = Date.now();
        console.log("Creating new user message with ID:", messageId);

        // Add user message with explicit properties
        const userMessage = {
          role: "user" as const,
          content: content,
          id: messageId,
          attachments: attachments || []
        };

        console.log("Adding user message:", userMessage);
        setMessages(prev => [...prev, userMessage]);

        // Create assistant message placeholder with explicit properties
        const assistantMessageId = messageId + 1;
        const assistantMessage = {
          role: "assistant" as const,
          content: "",
          id: assistantMessageId,
          attachments: []
        };

        console.log("Adding assistant placeholder:", assistantMessage);
        setMessages(prev => [...prev, assistantMessage]);

        // Send user message to backend
        await apiClient.post(`/chat/${chatId}/message`, {
          content,
          role: "user",
        });

        // Get the current auth token
        const token = await apiClient.getToken();

        // Start stream with token as query parameter - properly encode the token
        const streamUrl = token
          ? `${API_CONFIG.baseURL}/chat/${chatId}/stream?token=${encodeURIComponent(token)}`
          : `${API_CONFIG.baseURL}/chat/${chatId}/stream`;

        console.log(`Starting SSE connection to: ${streamUrl}`);
        const eventSource = new EventSource(streamUrl);

        eventSource.onmessage = (event) => {
          if (event.data === '[DONE]' || event.data === '[ERROR]') {
            eventSource.close();
            return;
          }

          console.log("Received SSE data:", event.data);

          setMessages(prev => {
            const newMessages = [...prev];
            // Find the assistant message by ID
            const assistantIndex = newMessages.findIndex(
              m => m.role === "assistant" && m.id === assistantMessageId
            );

            if (assistantIndex !== -1) {
              // Decode the escaped newlines
              const decodedContent = event.data.replace(/\\n/g, '\n');
              newMessages[assistantIndex] = {
                ...newMessages[assistantIndex],
                content: newMessages[assistantIndex].content + decodedContent,
                id: assistantMessageId // Keep the same ID
              };
            } else {
              console.warn("Could not find assistant message to update");
            }
            return newMessages;
          });
        };

        eventSource.onerror = (error) => {
          console.error('EventSource failed:', error);
          eventSource.close();

          // Check if this is an authentication error
          if (error instanceof ErrorEvent) {
            // Update the last message with an error notice
            setMessages(prev => {
              const newMessages = [...prev];
              const assistantIndex = newMessages.findIndex(
                m => m.role === "assistant" && m.id === assistantMessageId
              );

              if (assistantIndex !== -1 && !newMessages[assistantIndex].content) {
                // Only update if we haven't received any content yet
                newMessages[assistantIndex] = {
                  ...newMessages[assistantIndex],
                  content: "Failed to authenticate the streaming connection. Please try refreshing the page.",
                  id: assistantMessageId // Keep the same ID
                };
              }
              return newMessages;
            });
          }

          toast({
            title: "Error",
            description: "Failed to get response",
            variant: "destructive",
          });
        };

      } catch (error) {
        console.error("Error in handleSubmit:", error);
        toast({
          title: "Error",
          description: "Failed to get response",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [chatId, chatReady, toast]
  );

  const handleSourceChange = (sourceId: string) => {
    setSelectedSources((prev) => {
      if (prev.includes(sourceId)) {
        return prev.filter((id) => id !== sourceId);
      }
      return [...prev, sourceId];
    });
  };

  const handleUpdateSettings = async (settings: Partial<ModelSettings>) => {
    if (!chatId) return;

    const response = await apiClient.put(`/chat/${chatId}`, undefined, {
      model_settings: settings,  // Pass undefined for params, then the data
    });

    if (response.ok) {
      // Refresh chat info after updating settings
      try {
        const chatResponse = await apiClient.get(`/chat/${chatId}`);
        const chatData = await chatResponse.json();

        if (chatInfo) {
          setChatInfo({
            ...chatInfo,
            ...chatData
          });
        }
      } catch (error) {
        console.error("Failed to refresh chat info after settings update:", error);
      }
    } else {
      toast({
        title: "Error",
        description: "Failed to update settings",
        variant: "destructive",
      });
    }
  };

  // Check location state for create dialog and preselected sync
  useEffect(() => {
    const state = location.state as {
      showCreateDialog?: boolean;
      preselectedSyncId?: string;
    };

    if (state?.showCreateDialog) {
      setShowCreateDialog(true);
    }
  }, [location.state]);

  // Add this dialog component before the main return
  if (isOpenAIKeySet === false) {
    return (
      <Dialog
        open={true}
        onOpenChange={() => navigate('/dashboard')}
      >
        <DialogContent onEscapeKeyDown={() => navigate('/dashboard')} onInteractOutside={() => navigate('/dashboard')}>
          <DialogHeader>
            <DialogTitle>OpenAI API key required</DialogTitle>
            <DialogDescription>
              Please add your OpenAI API key to the .env file to continue using the chat functionality.
              <br />
              <br />
              Find the .env file in the root of the project and add the following: OPENAI_API_KEY=your_openai_api_key
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <div className={`flex h-full border-t ${resolvedTheme === 'dark' ? 'border-border/60' : 'border-border/80'} overflow-hidden`}>
      <ChatSidebar onCreateChat={() => setShowCreateDialog(true)} />
      <div className="flex-1 flex flex-col">
        {error ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <h2 className="text-lg font-semibold text-red-600">Error</h2>
              <p className="text-gray-600">{error}</p>
            </div>
          </div>
        ) : showCreateDialog ? (
          <CreateChatDialog
            open={showCreateDialog}
            preselectedSyncId={location.state?.preselectedSyncId}
            onOpenChange={setShowCreateDialog}
            onChatCreated={(newChatId) => {
              setShowCreateDialog(false);
              navigate(`/chat/${newChatId}`);
            }}
          />
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.length === 0 && !isLoading && (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  <p>No messages yet. Start a conversation!</p>
                </div>
              )}

              {messages.length > 0 && (
                <div className="space-y-6">
                  {messages.map((message, index) => (
                    <div key={`${message.id || index}-${index}`} className={cn(
                      "flex",
                      message.role === "user" ? "justify-end" : "justify-start"
                    )}>
                      <div className={cn(
                        "max-w-[80%]",
                        message.role === "user" ? "ml-auto" : "mr-auto"
                      )}>
                        <ChatMessage
                          role={message.role}
                          content={message.content || ""}
                          attachments={message.attachments}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {isLoading && messages.length === 0 && (
                <div className="flex justify-center">
                  <Spinner className="h-6 w-6" />
                </div>
              )}
            </div>
            <Card className="m-4 p-4">
              <ChatInput
                onSubmit={handleSubmit}
                isLoading={isLoading}
                disabled={!chatReady || !chatId}
              />
            </Card>
          </>
        )}
      </div>
      {chatInfo && (
        <ChatInfoSidebar
          chatInfo={chatInfo}
          onUpdateSettings={handleUpdateSettings}
        />
      )}
    </div>
  );
}

export default Chat;
