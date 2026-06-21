"use client"

import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Loader2, Bot, User, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

interface Message {
  id: number
  role: "user" | "assistant"
  content: string
  sources?: string[]
}

const EXAMPLE_PROMPTS = [
  "What is the STR filing timeline?",
  "KYC requirements for high-risk customers?",
  "PMLA cash transaction threshold?",
  "EDD obligations for PEPs?",
]

const MOCK_ANSWERS: Record<string, { content: string; sources: string[] }> = {
  default: {
    content: `Under the **RBI KYC Master Direction 2016** and the **Prevention of Money Laundering Act (PMLA) 2002**, financial institutions are required to:\n\n• File a **Suspicious Transaction Report (STR)** within **7 working days** of forming a suspicion.\n• The obligation applies to all Reporting Entities including banks, NBFCs, and payment system operators.\n• STRs must be filed with **FIU-IND** electronically through the FINnet portal.\n\nFor Enhanced Due Diligence (EDD) customers, the monitoring frequency must be increased, and STRs must be filed for all unusual patterns regardless of value.`,
    sources: ["PMLA Section 12A", "RBI KYC MD — Para 37", "FATF Recommendation 20"],
  },
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-blue-400"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  )
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user"
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn("flex gap-3", isUser ? "flex-row-reverse" : "flex-row")}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5",
          isUser ? "bg-blue-600" : "bg-slate-800 border border-slate-700"
        )}
      >
        {isUser
          ? <User className="w-4 h-4 text-white" />
          : <Bot className="w-4 h-4 text-blue-400" />
        }
      </div>

      {/* Content */}
      <div className={cn("max-w-[80%] flex flex-col gap-2", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "px-4 py-3 rounded-2xl text-sm leading-relaxed",
            isUser
              ? "bg-blue-600 text-white rounded-tr-sm"
              : "glass text-slate-200 rounded-tl-sm"
          )}
          // Render markdown-like bold
          dangerouslySetInnerHTML={{
            __html: msg.content
              .replace(/\*\*(.*?)\*\*/g, "<strong class='text-white'>$1</strong>")
              .replace(/•/g, "<span class='text-blue-400'>•</span>")
              .replace(/\n/g, "<br/>"),
          }}
        />
        {/* Source citations */}
        {msg.sources && msg.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {msg.sources.map((s, i) => (
              <span
                key={i}
                className="px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-xs text-blue-300 font-medium"
              >
                {s}
              </span>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

export function QueryInput() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      content: "Hello! I'm SIA-RAG, your AML compliance assistant. Ask me anything about PMLA, RBI KYC guidelines, FATF recommendations, or any other AML regulatory requirements.",
    },
  ])
  const [input, setInput]       = useState("")
  const [loading, setLoading]   = useState(false)
  const endRef                  = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const handleSend = async (text?: string) => {
    const q = (text ?? input).trim()
    if (!q || loading) return
    setInput("")

    const userMsg: Message = { id: Date.now(), role: "user", content: q }
    setMessages((m) => [...m, userMsg])
    setLoading(true)

    // Simulate backend response (replace with real fetch in prod)
    await new Promise((r) => setTimeout(r, 1600 + Math.random() * 800))

    const answer = MOCK_ANSWERS.default
    const assistantMsg: Message = {
      id: Date.now() + 1,
      role: "assistant",
      content: answer.content,
      sources: answer.sources,
    }
    setMessages((m) => [...m, assistantMsg])
    setLoading(false)
  }

  return (
    <section className="w-full max-w-3xl mx-auto" aria-label="Regulatory Assistant">
      {/* Chat window */}
      <div className="glass rounded-2xl overflow-hidden border border-white/[0.08]">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.07]">
          <div className="flex items-center gap-2.5">
            <div className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_6px_2px_rgba(52,211,153,0.5)]" />
            <span className="text-sm font-semibold text-white">Regulatory Assistant</span>
          </div>
          <span className="text-xs text-slate-500">LLaMA 3.3 70B · Hybrid RAG</span>
        </div>

        {/* Messages */}
        <div className="h-[360px] overflow-y-auto custom-scroll px-5 py-5 flex flex-col gap-5">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-3"
            >
              <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center">
                <Bot className="w-4 h-4 text-blue-400" />
              </div>
              <div className="glass px-4 py-3 rounded-2xl rounded-tl-sm">
                <TypingIndicator />
              </div>
            </motion.div>
          )}
          <div ref={endRef} />
        </div>

        {/* Example prompts */}
        <div className="px-5 pb-3 flex flex-wrap gap-2">
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => handleSend(p)}
              disabled={loading}
              className="px-3 py-1.5 rounded-full text-xs text-slate-400 border border-slate-700/60 hover:border-blue-500/40 hover:text-blue-300 hover:bg-blue-500/[0.07] transition-all duration-200 disabled:opacity-40"
              aria-label={`Ask: ${p}`}
            >
              {p}
            </button>
          ))}
        </div>

        {/* Input row */}
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2 bg-slate-900/70 border border-slate-700/60 rounded-xl px-4 py-3 focus-within:border-blue-500/50 transition-colors">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend()}
              placeholder="Ask an AML compliance question..."
              disabled={loading}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-500 outline-none disabled:opacity-50"
              aria-label="Ask an AML question"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center transition-all duration-200 hover:shadow-[0_0_14px_3px_hsla(217,91%,60%,0.35)]"
              aria-label="Send message"
            >
              {loading
                ? <Loader2 className="w-4 h-4 text-white animate-spin" />
                : <Send className="w-4 h-4 text-white" />
              }
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}
