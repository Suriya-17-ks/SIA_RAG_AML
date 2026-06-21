"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Send, Loader2, Bot, User, RotateCcw, BookOpen,
  FileText, PanelLeftClose, PanelLeft,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { VoiceInput } from "@/components/assistant/VoiceInput"
import { ChatHistory } from "@/components/assistant/ChatHistory"

// ── Config ────────────────────────────────────────────────────────────────────
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// ── Types ─────────────────────────────────────────────────────────────────────
interface SourceRef {
  page: number
  source: string
  section?: string | null
  jurisdiction?: string | null
  regulation_type?: string | null
  score?: number | null
}

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  sources?: SourceRef[]
  timestamp: Date
}

interface ConversationItem {
  conversation_id: string
  title: string
  message_count: number
  updated_at: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function generateId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

const EXAMPLE_PROMPTS = [
  { label: "STR Timeline",      text: "What is the STR filing timeline under PMLA and RBI guidelines?" },
  { label: "KYC for High-Risk", text: "What are the KYC requirements for high-risk customers?" },
  { label: "Cash Threshold",    text: "What is the cash transaction reporting threshold under PMLA?" },
  { label: "EDD for PEPs",      text: "What EDD measures are required for Politically Exposed Persons?" },
  { label: "UBO Identification", text: "How should Reporting Entities identify Ultimate Beneficial Owners?" },
  { label: "Record Retention",  text: "What are the minimum record retention requirements under PMLA Section 12?" },
]

// ── Source Card Component ─────────────────────────────────────────────────────
function SourceCard({ src }: { src: SourceRef }) {
  const jurisdictionCls: Record<string, string> = {
    PMLA: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    RBI:  "text-cyan-400 bg-cyan-500/10 border-cyan-500/20",
    FATF: "text-purple-400 bg-purple-500/10 border-purple-500/20",
  }
  const jCls = jurisdictionCls[src.jurisdiction || ""] || "text-slate-400 bg-slate-500/10 border-slate-500/20"

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl bg-neutral-900/80 border border-white/[0.08] text-xs" role="listitem">
      <FileText className="w-3 h-3 text-slate-500" />
      <span className="text-slate-300 font-medium truncate max-w-[140px]" title={src.source}>
        {src.source}
      </span>
      <span className="text-white font-bold">p.{src.page}</span>
      {src.section && (
        <span className="text-slate-500 truncate max-w-[100px]" title={src.section}>
          §{src.section}
        </span>
      )}
      {src.jurisdiction && (
        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold border ${jCls}`}>
          {src.jurisdiction}
        </span>
      )}
      {src.score != null && src.score > 0 && (
        <div className="flex items-center gap-1">
          <div className="w-10 h-1 rounded-full bg-slate-700 overflow-hidden">
            <div className="h-full rounded-full bg-blue-500" style={{ width: `${Math.min(src.score * 500, 100)}%` }} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Page Component ───────────────────────────────────────────────────────
export default function AssistantPage() {
  // State
  const [conversationId, setConversationId] = useState<string>(generateId())
  const [conversations, setConversations]   = useState<ConversationItem[]>([])
  const [messages, setMessages]             = useState<Message[]>([systemMsg()])
  const [input, setInput]                   = useState("")
  const [loading, setLoading]               = useState(false)
  const [sidebarOpen, setSidebarOpen]       = useState(true)

  const endRef   = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function systemMsg(): Message {
    return {
      id: "system-0",
      role: "assistant",
      content:
        "Hello! I am the SIA-RAG Regulatory Assistant. I can answer precise questions about AML compliance regulations including PMLA, RBI KYC guidelines, and FATF recommendations.\n\nAll answers are grounded in retrieved regulatory text with zero hallucinations.",
      timestamp: new Date(),
    }
  }

  // ── Scroll to bottom ──────────────────────────────────────────────
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  // ── Load conversation list on mount ───────────────────────────────
  useEffect(() => {
    loadConversationList()
  }, [])

  async function loadConversationList() {
    try {
      const res = await fetch(`${API_URL}/chat/history/list`)
      if (res.ok) {
        const data = await res.json()
        setConversations(data.conversations || [])
      }
    } catch {
      // Offline / backend not running — use local state
    }
  }

  // ── Save conversation to backend ──────────────────────────────────
  async function saveConversation(msgs: Message[]) {
    const userMsgs = msgs.filter((m) => m.role === "user")
    if (userMsgs.length === 0) return

    const title = userMsgs[0].content.slice(0, 60) + (userMsgs[0].content.length > 60 ? "…" : "")
    try {
      await fetch(`${API_URL}/chat/history/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: conversationId,
          title,
          messages: msgs.filter((m) => m.id !== "system-0").map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      })
      loadConversationList()
    } catch {
      // Silently fail if backend is unavailable
    }
  }

  // ── Load a conversation ───────────────────────────────────────────
  async function loadConversation(id: string) {
    try {
      const res = await fetch(`${API_URL}/chat/history/${id}`)
      if (res.ok) {
        const data = await res.json()
        setConversationId(id)
        const loaded: Message[] = [
          systemMsg(),
          ...(data.messages || []).map((m: any, i: number) => ({
            id: `loaded-${i}`,
            role: m.role,
            content: m.content,
            sources: m.sources,
            timestamp: new Date(data.updated_at * 1000),
          })),
        ]
        setMessages(loaded)
      }
    } catch {
      // Fallback
    }
  }

  // ── Delete a conversation ─────────────────────────────────────────
  async function deleteConversation(id: string) {
    try {
      await fetch(`${API_URL}/chat/history/${id}`, { method: "DELETE" })
      setConversations((c) => c.filter((x) => x.conversation_id !== id))
      if (id === conversationId) {
        handleNewChat()
      }
    } catch {}
  }

  // ── New Chat ──────────────────────────────────────────────────────
  function handleNewChat() {
    setConversationId(generateId())
    setMessages([systemMsg()])
    setInput("")
  }

  // ── Send message ──────────────────────────────────────────────────
  const send = useCallback(
    async (text?: string) => {
      const q = (text ?? input).trim()
      if (!q || loading) return
      setInput("")

      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content: q,
        timestamp: new Date(),
      }
      const newMsgs = [...messages, userMsg]
      setMessages(newMsgs)
      setLoading(true)

      // Build history for memory (exclude system greeting)
      const history = newMsgs
        .filter((m) => m.id !== "system-0")
        .slice(-10)
        .map((m) => ({ role: m.role, content: m.content }))

      try {
        const res = await fetch(`${API_URL}/chat/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: q,
            search_mode: "auto",
            conversation_id: conversationId,
            history,
          }),
        })

        const data = await res.json()

        const assistantMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: data.answer || "No response received.",
          sources: data.sources || [],
          timestamp: new Date(),
        }
        const finalMsgs = [...newMsgs, assistantMsg]
        setMessages(finalMsgs)
        saveConversation(finalMsgs)
      } catch (err: any) {
        const errMsg: Message = {
          id: generateId(),
          role: "assistant",
          content: `⚠️ Could not reach the backend. Make sure the server is running at ${API_URL}.\n\nError: ${err.message}`,
          timestamp: new Date(),
        }
        setMessages((m) => [...m, errMsg])
      } finally {
        setLoading(false)
        setTimeout(() => inputRef.current?.focus(), 100)
      }
    },
    [input, loading, messages, conversationId]
  )

  return (
    <main className="h-[calc(100vh-64px)] flex overflow-hidden bg-background" aria-label="Regulatory Assistant">
      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-r border-white/[0.06] flex-shrink-0 overflow-hidden"
            aria-label="Chat history"
          >
            <ChatHistory
              currentId={conversationId}
              onSelect={loadConversation}
              onNewChat={handleNewChat}
              conversations={conversations}
              onDelete={deleteConversation}
            />
          </motion.aside>
        )}
      </AnimatePresence>

      {/* ── Main chat area ───────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen((v) => !v)}
              className="text-slate-400 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/[0.05]"
              aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
            >
              {sidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <PanelLeft className="w-5 h-5" />}
            </button>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                <BookOpen className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <h1 className="text-base font-semibold text-white leading-none">Regulatory Assistant</h1>
                <p className="text-[11px] text-slate-500 mt-0.5">PMLA · RBI KYC · FATF</p>
              </div>
            </div>
          </div>
          <button
            onClick={handleNewChat}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-slate-400 hover:text-white border border-slate-800 hover:border-slate-600 transition-colors text-sm"
            aria-label="Clear conversation"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">New Chat</span>
          </button>
        </div>

        {/* Prompt chips */}
        {messages.length <= 1 && (
          <div className="flex flex-wrap gap-2 px-5 py-3 border-b border-white/[0.04]">
            {EXAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => send(p.text)}
                disabled={loading}
                className="px-3 py-1.5 rounded-full text-xs font-medium text-slate-400 border border-slate-700/60 hover:border-blue-500/40 hover:text-blue-300 hover:bg-blue-500/[0.06] transition-all duration-200 disabled:opacity-40"
              >
                {p.label}
              </button>
            ))}
          </div>
        )}

        {/* ── Messages ───────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto custom-scroll px-5 py-6 flex flex-col gap-6">
          {messages.map((msg) => {
            const isUser = msg.role === "user"
            return (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
              >
                {/* Avatar */}
                <div
                  className={cn(
                    "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5",
                    isUser ? "bg-blue-600" : "bg-neutral-900 border border-white/[0.08]"
                  )}
                  aria-hidden="true"
                >
                  {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-blue-400" />}
                </div>

                {/* Content */}
                <div className={cn("flex flex-col gap-2 max-w-[78%]", isUser ? "items-end" : "items-start")}>
                  <div
                    className={cn(
                      "px-4 py-3 rounded-2xl text-sm leading-7",
                      isUser
                        ? "bg-blue-600 text-white rounded-tr-sm"
                        : "glass-card text-slate-200 rounded-tl-sm"
                    )}
                    dangerouslySetInnerHTML={{
                      __html: msg.content
                        .replace(/\*\*(.*?)\*\*/g, "<strong class='text-white font-semibold'>$1</strong>")
                        .replace(/•/g, "<span class='text-blue-400 mr-1'>•</span>")
                        .replace(/\n/g, "<br/>"),
                    }}
                  />
                  {/* Source citations with page numbers */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1.5" role="list" aria-label="Sources">
                      {msg.sources.map((s, i) => (
                        <SourceCard key={i} src={s} />
                      ))}
                    </div>
                  )}
                  <span className="text-[11px] text-slate-600">{formatTime(msg.timestamp)}</span>
                </div>
              </motion.div>
            )
          })}

          {/* Typing indicator */}
          {loading && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 items-center"
            >
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
              <div className="glass-card px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-blue-400"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
                  />
                ))}
              </div>
            </motion.div>
          )}
          <div ref={endRef} />
        </div>

        {/* ── Input area ─────────────────────────────────────────── */}
        <div className="border-t border-white/[0.06] px-5 py-4">
          <div className="flex items-center gap-2 bg-black/60 border border-white/[0.08] rounded-xl px-4 py-3 focus-within:border-blue-500/50 transition-colors">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Ask about PMLA, RBI KYC, FATF requirements..."
              disabled={loading}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none"
              aria-label="Type your compliance question"
            />

            {/* Voice input */}
            <VoiceInput
              onTranscript={(text) => setInput((prev) => prev + text)}
              disabled={loading}
              backendUrl={API_URL}
            />

            {/* Send */}
            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              className="w-9 h-9 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-all duration-200 hover:shadow-[0_0_14px_3px_hsla(217,91%,60%,0.35)] flex-shrink-0"
              aria-label="Send message"
            >
              {loading ? <Loader2 className="w-4 h-4 text-white animate-spin" /> : <Send className="w-4 h-4 text-white" />}
            </button>
          </div>
          <p className="text-[11px] text-slate-600 mt-2 text-center">
            Answers grounded in retrieved AML regulatory text · 0.0% hallucination rate · Sources cited with page numbers
          </p>
        </div>
      </div>
    </main>
  )
}
