import { useState, useEffect, useCallback } from "react";
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
  const { chatId } = useParams<{ chatId: string }>();

  // Check for chatId and load first chat if needed
  useEffect(() => {
    async function initializeChat() {
      try {
        // Use the same endpoint as ChatSidebar
        const response = await apiClient.get('/chat');
        const chats = await response.json();

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
      } catch (error) {
        console.error("Failed to initialize chat:", error);
        toast({
          title: "Error",
          description: "Failed to load chats. Please try again.",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    }

    void initializeChat();
  }, [chatId, navigate, toast]);

  // Load chat data on mount or when chatId changes
  useEffect(() => {
    async function loadChat() {
      if (!chatId) return;
      try {
        setIsLoading(true);
        setError(null);
        const resp = await apiClient.get(`/chat/${chatId}`);

        if (!resp.ok) {
          throw new Error(`Failed to load chat: ${resp.statusText}`);
        }

        // Handle the response data directly
        const chatData = await resp.json();

        // Ensure messages is an array, even if empty
        const messages = chatData.messages || [];

        setMessages(messages.map((m: any) => ({
          role: m.role || 'user',
          content: m.content,
          attachments: m.attachments || [],
          id: m.id || Date.now(),
        })));
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
    void loadChat();
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
      if (!chatId) return;

      try {
        // Add user message
        const userMessage: Message = {
          role: "user",
          content,
          id: Date.now(),
          attachments: attachments
        };
        setMessages(prev => [...prev, userMessage]);

        // Create assistant message placeholder
        const assistantMessage: Message = {
          role: "assistant",
          content: "",
          id: Date.now() + 1,
          attachments: []
        };
        setMessages(prev => [...prev, assistantMessage]);

        // Send user message to backend
        await apiClient.post(`/chat/${chatId}/message`, {
          content,
          role: "user",
        });

        // Start stream
        const eventSource = new EventSource(`${API_CONFIG.baseURL}/chat/${chatId}/stream`);

        eventSource.onmessage = (event) => {
          if (event.data === '[DONE]' || event.data === '[ERROR]') {
            eventSource.close();
            return;
          }

          setMessages(prev => {
            const newMessages = [...prev];
            const lastMessage = newMessages[newMessages.length - 1];
            // Decode the escaped newlines
            const decodedContent = event.data.replace(/\\n/g, '\n');
            newMessages[newMessages.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + decodedContent,
              id: Date.now()
            };
            return newMessages;
          });
        };

        eventSource.onerror = (error) => {
          console.error('EventSource failed:', error);
          eventSource.close();
          toast({
            title: "Error",
            description: "Failed to get response",
            variant: "destructive",
          });
        };

      } catch (error) {
        console.error(error);
        toast({
          title: "Error",
          description: "Failed to get response",
          variant: "destructive",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [chatId, toast]
  );

  const handleSourceChange = (sourceId: string) => {
    setSelectedSources((prev) => {
      if (prev.includes(sourceId)) {
        return prev.filter((id) => id !== sourceId);
      }
      return [...prev, sourceId];
    });
  };

  useEffect(() => {
    if (chatId) {
      void loadChatInfo();
    }
  }, [chatId]);

  const loadChatInfo = async () => {
    try {
      // Get chat info
      const chatResponse = await apiClient.get(`/chat/${chatId}`);
      const chatData = await chatResponse.json();

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
    } catch (error) {
      console.error("Failed to load chat info:", error);
    }
  };

  const handleUpdateSettings = async (settings: Partial<ModelSettings>) => {
    if (!chatId) return;

    const response = await apiClient.put(`/chat/${chatId}`, undefined, {
      model_settings: settings,  // Pass undefined for params, then the data
    });

    if (response.ok) {
      await loadChatInfo();
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

  // Add this effect at the top of other effects
  useEffect(() => {
    async function checkOpenAIKey() {
      try {
        const response = await apiClient.get('/chat/openai_key_set');
        const isSet = await response.json();
        setIsOpenAIKeySet(isSet);
      } catch (error) {
        console.error("Failed to check OpenAI key:", error);
        setIsOpenAIKeySet(false);
      }
    }

    void checkOpenAIKey();
  }, []);

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
              {messages.map((message, index) => (
                <div key={message.id} className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}>
                  <div className={cn(
                    "max-w-[80%]",
                    message.role === "user" ? "ml-auto" : "mr-auto"
                  )}>
                    <ChatMessage
                      role={message.role}
                      content={message.content}
                      attachments={message.attachments}
                    />
                  </div>
                </div>
              ))}

              {isLoading && (
                <div className="flex justify-center">
                  <Spinner className="h-6 w-6" />
                </div>
              )}
            </div>
            <Card className="m-4 p-4">
              <ChatInput onSubmit={handleSubmit} isLoading={isLoading} />
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
