"use client";

import { FormEvent, useEffect, useState, useRef } from "react";
import { toast } from "sonner";
import { Send, Plus, MessageSquare, Bot, User, Bookmark, ThumbsUp, ThumbsDown, Copy, Check } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";

import { 
  listChatSessions, 
  listChatMessages, 
  createChatSession, 
  sendChatMessage, 
  updateChatMessage 
} from "@/lib/api/client";
import type { ProjectRole } from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";
import { getActiveProject } from "@/lib/project-store";

import { useCitationViewer } from "@/components/citation-viewer-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { PageWrapper } from "@/components/layout/page-wrapper";

export function QueryConsole() {
  const queryClient = useQueryClient();
  const { openCitation } = useCitationViewer();
  const [activeProjectId, setActiveProjectId] = useState("");
  const [activeProjectRole, setActiveProjectRole] = useState<ProjectRole | null>(null);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const active = getActiveProject();
    if (active) {
      setActiveProjectId(active.id);
      setActiveProjectRole(active.role ?? "viewer");
    }
  }, []);

  const canMutateProject = canEditProject(activeProjectRole);

  // Fetch Sessions
  const { data: sessionsData, isLoading: loadingSessions } = useQuery({
    queryKey: ["chat_sessions", activeProjectId],
    queryFn: () => listChatSessions(activeProjectId),
    enabled: !!activeProjectId,
  });
  const sessions = sessionsData?.data.items || [];

  // Fetch Messages for active session
  const { data: messagesData, isLoading: loadingMessages } = useQuery({
    queryKey: ["chat_messages", activeSessionId],
    queryFn: () => listChatMessages(activeSessionId!),
    enabled: !!activeSessionId,
    refetchInterval: sending ? 2000 : false, // Poll if we are awaiting a response 
  });
  const messages = messagesData?.data.items || [];

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Set initial active session if none selected
  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId && !loadingSessions) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId, loadingSessions]);

  async function handleNewChat() {
    if (!canMutateProject) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    setActiveSessionId(null);
    setInputValue("");
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!inputValue.trim()) return;
    if (!activeProjectId) {
      toast.error("Please select a project first.");
      return;
    }
    if (!canMutateProject) {
      toast.error("Sending messages requires editor role or higher.");
      return;
    }

    const content = inputValue.trim();
    setInputValue("");
    setSending(true);

    let currentSessionId = activeSessionId;

    try {
      // 1. Create session if needed
      if (!currentSessionId) {
        const title = content.length > 30 ? content.substring(0, 30) + "..." : content;
        const res = await createChatSession({ projectId: activeProjectId, title });
        currentSessionId = res.data.id;
        setActiveSessionId(currentSessionId);
        await queryClient.invalidateQueries({ queryKey: ["chat_sessions", activeProjectId] });
      }

      // Optimistic update for UI feel (optional, but good for UX)
      // Here we just let React Query handle it or we wait for the real response.
      // Since `sendChatMessage` blocks until the RAG is done, we must wait.

      // 2. Send message
      await sendChatMessage({
        sessionId: currentSessionId,
        content: content,
        provider: "openai", // Could make this a setting
        topK: 5,
      });

      await queryClient.invalidateQueries({ queryKey: ["chat_messages", currentSessionId] });
      await queryClient.invalidateQueries({ queryKey: ["chat_sessions", activeProjectId] }); // in case title updated

    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  // --- Message Actions ---
  const [copiedId, setCopiedId] = useState<string | null>(null);
  
  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleAction = async (msgId: string, action: "bookmark" | "thumbUp" | "thumbDown", currentValue: any) => {
    if (!canMutateProject) {
      toast.error("This action requires editor role or higher.");
      return;
    }
    let payload: any = {};
    if (action === "bookmark") payload.isBookmarked = !currentValue;
    if (action === "thumbUp") payload.rating = currentValue === 1 ? 0 : 1;
    if (action === "thumbDown") payload.rating = currentValue === -1 ? 0 : -1;

    try {
      await updateChatMessage({ messageId: msgId, ...payload });
      await queryClient.invalidateQueries({ queryKey: ["chat_messages", activeSessionId] });
    } catch {
      toast.error("Failed to update message.");
    }
  };

  const handleCitationClick = (citation: any) => {
    if (citation.source_type === "file" && citation.source_id) {
      openCitation(citation);
      return;
    }
    if (citation.url) {
      window.open(citation.url, "_blank", "noopener,noreferrer");
    }
  };

  if (!activeProjectId) {
    return (
      <PageWrapper title="Query Console" description="Ask questions about your data.">
        <Card className="border-dashed shadow-none bg-muted/30">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="rounded-full bg-primary/10 p-3 mb-4">
              <MessageSquare className="h-6 w-6 text-primary" />
            </div>
            <h3 className="text-lg font-medium mb-1">No Active Project</h3>
            <p className="text-sm text-muted-foreground max-w-sm mb-4">
              You need to select or create a project before you can query your sources.
            </p>
            <Button onClick={() => window.location.href = "/projects"}>Go to Projects</Button>
          </CardContent>
        </Card>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper
      title="Chat"
      description="Chat with your documents using RAG."
      className="pb-0" // Remove bottom padding for full height chat
    >
      {!canMutateProject ? (
        <div className="mb-4 rounded-md border border-amber-300/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
          You have viewer access for this project. Starting chats, sending messages, bookmarking, and rating are disabled.
        </div>
      ) : null}

      <div className="flex h-[calc(100vh-140px)] gap-6 overflow-hidden">
        
        {/* Left Sidebar (Sessions) */}
        <div className="w-64 flex-col gap-4 border-r pr-4 hidden md:flex h-full">
          <Button
            onClick={handleNewChat}
            className="w-full gap-2 justify-start mb-2"
            variant="outline"
            disabled={!canMutateProject}
            title={canMutateProject ? undefined : "Requires editor role"}
          >
            <Plus className="h-4 w-4" /> New Chat
          </Button>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-1">
            {loadingSessions ? (
              <div className="flex justify-center p-4"><Spinner size="sm" /></div>
            ) : sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No chat history.</p>
            ) : (
              sessions.map(s => (
                <div 
                  key={s.id}
                  onClick={() => setActiveSessionId(s.id)}
                  className={`px-3 py-2 rounded-md text-sm cursor-pointer transition-colors truncate ${
                    activeSessionId === s.id 
                      ? 'bg-primary text-primary-foreground font-medium' 
                      : 'hover:bg-accent text-foreground/80'
                  }`}
                >
                  {s.title || "New Chat"}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col relative h-full bg-card rounded-xl border shadow-sm">
          
          {/* Header */}
          <div className="h-14 border-b flex items-center px-6 shrink-0 bg-muted/20">
            <h3 className="font-medium text-sm">
              {activeSessionId 
                ? sessions.find(s => s.id === activeSessionId)?.title || "Chat Session"
                : "New Chat Session"
              }
            </h3>
          </div>

          {/* Messages Scroll View */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6 scroll-smooth">
            {!activeSessionId && !sending && (
              <div className="h-full flex flex-col items-center justify-center text-center opacity-50 max-w-md mx-auto">
                <Bot className="h-12 w-12 mb-4" />
                <h2 className="text-xl font-semibold mb-2">How can I help you today?</h2>
                <p className="text-sm">Ask a question about your project's sources.</p>
              </div>
            )}

            {loadingMessages && activeSessionId && messages.length === 0 ? (
              <div className="flex justify-center p-8"><Spinner /></div>
            ) : (
              messages.map(msg => (
                <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                  
                  {/* Avatar */}
                  <div className={`shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
                    msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted border text-foreground'
                  }`}>
                    {msg.role === 'user' ? <User className="h-5 w-5" /> : <Bot className="h-5 w-5" />}
                  </div>

                  {/* Bubble */}
                  <div className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    <div className={`px-4 py-3 rounded-2xl ${
                      msg.role === 'user' 
                        ? 'bg-primary text-primary-foreground rounded-tr-sm' 
                        : 'bg-muted/50 border rounded-tl-sm text-foreground prose prose-sm dark:prose-invert max-w-none'
                    }`}>
                      {msg.role === 'user' ? (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      ) : (
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      )}
                    </div>

                    {/* Citations & Actions (Assistant only) */}
                    {msg.role === 'assistant' && (
                      <div className="flex flex-col gap-2 mt-2 w-full">
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {msg.citations.map((cit, idx) => (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => handleCitationClick(cit)}
                                className="inline-flex"
                              >
                                <Badge variant="outline" className="cursor-pointer text-[10px] bg-background">
                                  [{idx + 1}] {cit.title || cit.source_id.substring(0,6)}
                                  {cit.page_number ? ` · p.${cit.page_number}` : ""}
                                </Badge>
                              </button>
                            ))}
                          </div>
                        )}
                        
                        <div className="flex items-center gap-1 mt-1 opacity-60 hover:opacity-100 transition-opacity">
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleCopy(msg.content, msg.id)}>
                            {copiedId === msg.id ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleAction(msg.id, "thumbUp", msg.rating)}>
                            <ThumbsUp className={`h-3.5 w-3.5 ${msg.rating === 1 ? 'fill-current text-primary' : ''}`} />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => handleAction(msg.id, "thumbDown", msg.rating)}>
                            <ThumbsDown className={`h-3.5 w-3.5 ${msg.rating === -1 ? 'fill-current text-destructive' : ''}`} />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7 ml-1" onClick={() => handleAction(msg.id, "bookmark", msg.is_bookmarked)}>
                            <Bookmark className={`h-3.5 w-3.5 ${msg.is_bookmarked ? 'fill-current text-primary' : ''}`} />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {sending && (
              <div className="flex gap-4 flex-row">
                <div className="shrink-0 h-8 w-8 rounded-full flex items-center justify-center bg-muted border text-foreground">
                  <Bot className="h-5 w-5" />
                </div>
                <div className="flex flex-col max-w-[85%] items-start">
                  <div className="px-4 py-4 rounded-2xl bg-muted/50 border rounded-tl-sm flex items-center gap-2">
                    <Spinner size="sm" /> 
                    <span className="text-sm text-muted-foreground animate-pulse">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} className="h-1" />
          </div>

          {/* Input Area */}
          <div className="p-4 bg-background border-t mt-auto rounded-b-xl">
            <form onSubmit={handleSubmit} className="flex gap-2 max-w-4xl mx-auto">
              <Input 
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                placeholder="Message NoteMesh..."
                className="flex-1 bg-muted/20 border-muted-foreground/20 focus-visible:ring-primary/50 text-base py-5 px-4 rounded-full"
                disabled={sending || !canMutateProject}
              />
              <Button
                type="submit"
                disabled={!inputValue.trim() || sending || !canMutateProject}
                size="icon"
                className="h-[42px] w-[42px] rounded-full shrink-0 shadow-sm border border-transparent hover:border-border"
                title={canMutateProject ? undefined : "Requires editor role"}
              >
                {sending ? <Spinner size="sm" className="text-primary-foreground" /> : <Send className="h-5 w-5 ml-0.5" />}
              </Button>
            </form>
            <div className="text-center mt-2 text-[10px] text-muted-foreground/60 w-full truncate">
              AI can make mistakes. NoteMesh uses RAG powered by selected provider (openai).
            </div>
          </div>
          
        </div>
      </div>
    </PageWrapper>
  );
}
