"use client";

import { FormEvent, useEffect, useState, useRef, useCallback } from "react";
import { toast } from "sonner";
import {
  Send,
  Plus,
  Bot,
  User,
  Bookmark,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  MessageSquare,
  Zap,
  ChevronDown,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";

import {
  listChatSessions,
  listChatMessages,
  createChatSession,
  sendChatMessage,
  updateChatMessage,
} from "@/lib/api/client";
import type { ProjectRole } from "@/lib/api/types";
import { canEditProject } from "@/lib/permissions";


import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import type { KnowledgeNode } from "./cockpit-knowledge-panel";

// Quick command suggestions
const QUICK_COMMANDS = [
  { label: "⚔️ Debate", template: "Debate the main conflicting arguments in my documents" },
  { label: "🔍 Compare", template: "Compare and contrast the key findings across sources" },
  { label: "⚠️ Risks", template: "Identify the top risks and mitigation strategies" },
  { label: "📋 Summary", template: "Give me an executive brief of all documents" },
];

interface CockpitChatPanelProps {
  projectId: string;
  projectRole: ProjectRole | null;
  onConceptsExtracted?: (nodes: KnowledgeNode[]) => void;
  onCitationActivated?: (citation: any) => void;
}

function extractConceptsFromMessage(content: string, messageId: string): KnowledgeNode[] {
  // Simple heuristic: extract noun phrases in bold/header, or sentences with key terms
  const candidates: string[] = [];

  // Extract **bold** terms
  const boldMatches = content.match(/\*\*([^*]{3,40})\*\*/g) || [];
  boldMatches.forEach((m) => candidates.push(m.replace(/\*\*/g, "").trim()));

  // Extract ## headings
  const headingMatches = content.match(/#{1,3}\s+(.+)/g) || [];
  headingMatches.forEach((m) => candidates.push(m.replace(/#{1,3}\s+/, "").trim()));

  // Fallback 1: Extract capitalized multi-word phrases (e.g., "Machine Learning", "Vietnam Airlines")
  if (candidates.length < 3) {
    const capsMatches = content.match(/([A-Z][a-zA-Z0-9-]+\s+[A-Z][a-zA-Z0-9-]+)/g) || [];
    capsMatches.forEach((m) => candidates.push(m.trim()));
  }

  // Fallback 2: Extract long interesting words if still empty
  if (candidates.length === 0) {
    const words = content.split(/[\s.,!?;:"'()[\]]+/).filter((w) => w.length >= 7);
    words.slice(0, 5).forEach((w) => candidates.push(w));
  }

  // Fallback 3: Just take the first few words if it's super short
  if (candidates.length === 0) {
    const words = content.split(/\s+/).filter((w) => w.length > 4);
    words.slice(0, 3).forEach((w) => candidates.push(w));
  }

  if (candidates.length === 0) return [];

  const unique = Array.from(new Set(candidates)).filter(Boolean).slice(0, 8);
  return unique.map((label, idx) => ({
    id: `${messageId}-${idx}`,
    label,
    type: label.toLowerCase().includes("risk") || label.toLowerCase().includes("conflict")
      ? "conflict"
      : "concept",
    weight: 0.4 + Math.random() * 0.4,
    connections: idx > 0 ? [`${messageId}-${idx - 1}`] : [],
  }));
}

export function CockpitChatPanel({
  projectId,
  projectRole,
  onConceptsExtracted,
  onCitationActivated,
}: CockpitChatPanelProps) {
  const queryClient = useQueryClient();


  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");
  const [sending, setSending] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const canMutate = canEditProject(projectRole);

  const { data: sessionsData, isLoading: loadingSessions } = useQuery({
    queryKey: ["chat_sessions", projectId],
    queryFn: () => listChatSessions(projectId),
    enabled: !!projectId,
  });
  const sessions = sessionsData?.data.items || [];

  const { data: messagesData, isLoading: loadingMessages } = useQuery({
    queryKey: ["chat_messages", activeSessionId],
    queryFn: () => listChatMessages(activeSessionId!),
    enabled: !!activeSessionId,
    refetchInterval: sending ? 2000 : false,
  });
  const messages = messagesData?.data.items || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (sessions.length > 0 && !activeSessionId && !loadingSessions) {
      setActiveSessionId(sessions[0].id);
    }
  }, [sessions, activeSessionId, loadingSessions]);

  // Extract concepts from latest AI message
  useEffect(() => {
    if (!onConceptsExtracted || messages.length === 0) return;
    const assistantMsgs = messages.filter((m) => m.role === "assistant");
    if (assistantMsgs.length === 0) return;
    const latest = assistantMsgs[assistantMsgs.length - 1];
    const concepts = extractConceptsFromMessage(latest.content, latest.id);
    if (concepts.length > 0) onConceptsExtracted(concepts);
  }, [messages, onConceptsExtracted]);

  async function handleNewChat() {
    if (!canMutate) {
      toast.error("Editor role required.");
      return;
    }
    setActiveSessionId(null);
    setInputValue("");
    setShowSessions(false);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!inputValue.trim() || !projectId || !canMutate) return;

    const content = inputValue.trim();
    setInputValue("");
    setSending(true);

    let currentSessionId = activeSessionId;

    try {
      if (!currentSessionId) {
        const title = content.length > 30 ? content.substring(0, 30) + "…" : content;
        const res = await createChatSession({ projectId, title });
        currentSessionId = res.data.id;
        setActiveSessionId(currentSessionId);
        await queryClient.invalidateQueries({ queryKey: ["chat_sessions", projectId] });
      }

      await sendChatMessage({
        sessionId: currentSessionId,
        content,
        provider: "openai",
        topK: 5,
      });

      await queryClient.invalidateQueries({ queryKey: ["chat_messages", currentSessionId] });
      await queryClient.invalidateQueries({ queryKey: ["chat_sessions", projectId] });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setSending(false);
    }
  }

  const handleCopy = useCallback((text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const handleAction = useCallback(
    async (msgId: string, action: "bookmark" | "thumbUp" | "thumbDown", currentValue: any) => {
      if (!canMutate) return;
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
    },
    [canMutate, queryClient, activeSessionId]
  );

  const handleCitationClick = useCallback(
    (citation: any) => {
      if (citation.source_type === "file" && citation.source_id) {
        onCitationActivated?.(citation);
      } else if (citation.url) {
        window.open(citation.url, "_blank", "noopener,noreferrer");
      }
    },
    [onCitationActivated]
  );

  const handleQuickCommand = (template: string) => {
    setInputValue(template);
    inputRef.current?.focus();
  };

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  return (
    <div className="flex h-full flex-col bg-white dark:bg-[#0D1117]">
      {/* Top toolbar */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-200 dark:border-white/5 shrink-0">
        {/* Session switcher */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setShowSessions((v) => !v)}
            className="flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium text-slate-700 dark:text-white/70 hover:bg-slate-100 dark:hover:bg-white/5 border border-slate-200 dark:border-white/10 transition-colors max-w-[160px]"
          >
            <MessageSquare className="h-3.5 w-3.5 text-[#6c63ff] shrink-0" />
            <span className="truncate">{activeSession?.title || "New conversation"}</span>
            <ChevronDown className="h-3 w-3 shrink-0 ml-auto" />
          </button>

          {showSessions && (
            <div className="absolute top-full left-0 mt-1 z-50 w-64 rounded-xl border border-slate-200 dark:border-white/10 bg-white dark:bg-[#161b27] shadow-xl dark:shadow-2xl overflow-hidden">
              <div className="p-2 border-b border-slate-200 dark:border-white/5">
                <button
                  type="button"
                  onClick={handleNewChat}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-slate-600 dark:text-white/70 hover:bg-slate-100 dark:hover:bg-white/5 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5 text-[#6c63ff]" />
                  New conversation
                </button>
              </div>
              <div className="max-h-48 overflow-y-auto p-2">
                {loadingSessions ? (
                  <div className="flex justify-center p-3">
                    <Spinner size="sm" />
                  </div>
                ) : sessions.length === 0 ? (
                  <p className="text-center py-3 text-xs text-slate-400 dark:text-white/30">No history yet</p>
                ) : (
                  sessions.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => {
                        setActiveSessionId(s.id);
                        setShowSessions(false);
                      }}
                      className={`flex w-full items-center rounded-lg px-3 py-2 text-xs text-left transition-colors ${
                        activeSessionId === s.id
                          ? "bg-[#6c63ff]/10 dark:bg-[#6c63ff]/20 text-[#6c63ff]"
                          : "text-slate-500 dark:text-white/50 hover:bg-slate-100 dark:hover:bg-white/5"
                      }`}
                    >
                      <span className="truncate">{s.title || "New Chat"}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        <div className="ml-auto flex items-center gap-1">
          {!canMutate && (
            <Badge
              variant="outline"
              className="text-[10px] border-amber-500/40 text-amber-400/70 bg-amber-500/10"
            >
              Viewer
            </Badge>
          )}
          <div className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" title="RAG Ready" />
        </div>
      </div>

      {/* Quick command chips */}
      <div className="flex gap-1.5 px-4 py-2 border-b border-slate-200 dark:border-white/5 overflow-x-auto shrink-0 scrollbar-none">
        {QUICK_COMMANDS.map((cmd) => (
          <button
            key={cmd.label}
            type="button"
            onClick={() => handleQuickCommand(cmd.template)}
            disabled={!canMutate}
            className="flex-shrink-0 rounded-full px-3 py-1 text-[11px] font-medium bg-slate-100 dark:bg-white/5 hover:bg-[#6c63ff]/10 border border-slate-200 dark:border-white/10 hover:border-[#6c63ff]/40 text-slate-600 dark:text-white/60 hover:text-[#6c63ff] dark:hover:text-[#6c63ff] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {cmd.label}
          </button>
        ))}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5 scroll-smooth min-h-0">
        {!activeSessionId && !sending ? (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-60 gap-3">
            <div className="relative">
              <div className="absolute inset-0 rounded-full bg-[#6c63ff]/20 blur-xl" />
              <div className="relative h-14 w-14 rounded-2xl bg-[#6c63ff]/10 border border-[#6c63ff]/30 flex items-center justify-center">
                <Bot className="h-7 w-7 text-[#6c63ff]" />
              </div>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-800 dark:text-white/80">Research Cockpit Ready</h3>
              <p className="text-xs text-slate-500 dark:text-white/40 mt-1 max-w-[240px]">
                Ask anything about your documents. Citations will appear in the Evidence Panel →
              </p>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400 dark:text-white/30 mt-2">
              <Zap className="h-3 w-3 text-[#6c63ff]" />
              RAG-powered · Source-grounded answers
            </div>
          </div>
        ) : null}

        {loadingMessages && activeSessionId && messages.length === 0 ? (
          <div className="flex justify-center p-8">
            <Spinner />
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div
                className={`shrink-0 h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold ${
                  msg.role === "user"
                    ? "bg-[#6c63ff] text-white"
                    : "bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10 text-slate-600 dark:text-white/60"
                }`}
              >
                {msg.role === "user" ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </div>

              {/* Bubble */}
              <div
                className={`flex flex-col max-w-[82%] ${
                  msg.role === "user" ? "items-end" : "items-start"
                }`}
              >
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-[#6c63ff] text-white rounded-tr-sm"
                      : "bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 rounded-tl-sm text-slate-800 dark:text-white/85 prose prose-slate dark:prose-invert prose-sm max-w-none"
                  }`}
                >
                  {msg.role === "user" ? (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                </div>

                {/* Assistant actions & citations */}
                {msg.role === "assistant" && (
                  <div className="flex flex-col gap-2 mt-1.5 w-full">
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {msg.citations.map((cit, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => handleCitationClick(cit)}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium bg-[#00d8ff]/10 border border-[#00d8ff]/30 text-[#00d8ff] hover:bg-[#00d8ff]/20 transition-colors cursor-pointer"
                          >
                            [{idx + 1}] {cit.title || cit.source_id?.substring(0, 8)}
                            {cit.page_number ? ` · p.${cit.page_number}` : ""}
                          </button>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center gap-0.5 opacity-50 hover:opacity-100 transition-opacity">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-slate-400 dark:text-white/50 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10"
                        onClick={() => handleCopy(msg.content, msg.id)}
                      >
                        {copiedId === msg.id ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-slate-400 dark:text-white/50 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10"
                        onClick={() => handleAction(msg.id, "thumbUp", msg.rating)}
                      >
                        <ThumbsUp
                          className={`h-3 w-3 ${msg.rating === 1 ? "fill-current text-[#6c63ff]" : ""}`}
                        />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-slate-400 dark:text-white/50 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10"
                        onClick={() => handleAction(msg.id, "thumbDown", msg.rating)}
                      >
                        <ThumbsDown
                          className={`h-3 w-3 ${msg.rating === -1 ? "fill-current text-[#ff6b35]" : ""}`}
                        />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6 text-slate-400 dark:text-white/50 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-white/10"
                        onClick={() => handleAction(msg.id, "bookmark", msg.is_bookmarked)}
                      >
                        <Bookmark
                          className={`h-3 w-3 ${msg.is_bookmarked ? "fill-current text-[#6c63ff]" : ""}`}
                        />
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))
        )}

        {sending && (
          <div className="flex gap-3 flex-row">
            <div className="shrink-0 h-7 w-7 rounded-full flex items-center justify-center bg-slate-100 dark:bg-white/5 border border-slate-200 dark:border-white/10">
              <Bot className="h-4 w-4 text-slate-400 dark:text-white/60" />
            </div>
            <div className="flex flex-col items-start">
              <div className="px-4 py-3 rounded-2xl rounded-tl-sm bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 flex items-center gap-2">
                {/* Pulsing dots animation */}
                <div className="flex gap-1">
                  {[0, 0.2, 0.4].map((delay) => (
                    <div
                      key={delay}
                      className="h-1.5 w-1.5 rounded-full bg-[#6c63ff]"
                      style={{ animation: `cockpit-bounce 1.2s ${delay}s infinite ease-in-out` }}
                    />
                  ))}
                </div>
                <span className="text-xs text-slate-400 dark:text-white/40">Searching knowledge base…</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} className="h-1" />
      </div>

      {/* Input */}
      <div className="shrink-0 p-3 border-t border-slate-200 dark:border-white/5 bg-white dark:bg-[#0D1117]">
        <form onSubmit={handleSubmit} className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={canMutate ? "Ask about your documents…" : "Viewer access — read only"}
              disabled={sending || !canMutate}
              className="w-full rounded-xl bg-slate-50 dark:bg-white/5 border border-slate-200 dark:border-white/10 px-4 py-3 text-sm text-slate-800 dark:text-white/90 placeholder:text-slate-400 dark:placeholder:text-white/25 focus:outline-none focus:ring-2 focus:ring-[#6c63ff]/50 focus:border-[#6c63ff]/40 transition-all disabled:opacity-40"
            />
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || sending || !canMutate}
            className="shrink-0 flex h-11 w-11 items-center justify-center rounded-xl bg-[#6c63ff] text-white shadow-lg shadow-[#6c63ff]/30 hover:bg-[#6c63ff]/90 disabled:opacity-40 disabled:cursor-not-allowed transition-all hover:scale-105 active:scale-95"
          >
            {sending ? (
              <Spinner size="sm" className="text-white" />
            ) : (
              <Send className="h-4 w-4 ml-0.5" />
            )}
          </button>
        </form>
        <p className="text-center mt-1.5 text-[10px] text-slate-400 dark:text-white/20">
          NoteMesh RAG · Evidence-grounded responses
        </p>
      </div>
    </div>
  );
}
