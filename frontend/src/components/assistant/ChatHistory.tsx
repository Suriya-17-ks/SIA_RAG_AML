"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { MessageSquare, Plus, Trash2, Clock } from "lucide-react"
import { cn } from "@/lib/utils"

interface ConversationItem {
  conversation_id: string
  title: string
  message_count: number
  updated_at: number
}

interface ChatHistoryProps {
  currentId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  conversations: ConversationItem[]
  onDelete?: (id: string) => void
}

function timeAgo(ts: number): string {
  const diff = Date.now() / 1000 - ts
  if (diff < 60) return "Just now"
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export function ChatHistory({
  currentId,
  onSelect,
  onNewChat,
  conversations,
  onDelete,
}: ChatHistoryProps) {
  return (
    <div className="flex flex-col h-full">
      {/* New Chat button */}
      <button
        onClick={onNewChat}
        className="flex items-center gap-2 px-4 py-3 mx-3 mt-3 rounded-xl border border-dashed border-slate-700/60 text-sm font-medium text-slate-400 hover:text-white hover:border-blue-500/40 hover:bg-blue-500/[0.05] transition-all duration-200"
        aria-label="Start new conversation"
      >
        <Plus className="w-4 h-4" />
        New Chat
      </button>

      {/* Conversations list */}
      <div className="flex-1 overflow-y-auto custom-scroll mt-3 px-2 space-y-1">
        {conversations.length === 0 && (
          <p className="text-xs text-slate-600 px-3 py-6 text-center">
            No conversations yet
          </p>
        )}
        {conversations.map((conv) => (
          <motion.div
            key={conv.conversation_id}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            className="group"
          >
            <button
              onClick={() => onSelect(conv.conversation_id)}
              className={cn(
                "w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all duration-150 flex items-start gap-2.5",
                currentId === conv.conversation_id
                  ? "bg-blue-600/15 text-blue-200 border border-blue-500/20"
                  : "text-slate-400 hover:text-white hover:bg-white/[0.04]"
              )}
              aria-current={currentId === conv.conversation_id ? "page" : undefined}
            >
              <MessageSquare className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">{conv.title}</p>
                <p className="text-[11px] text-slate-600 mt-0.5 flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timeAgo(conv.updated_at)} · {conv.message_count} msgs
                </p>
              </div>
              {/* Delete button */}
              {onDelete && (
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    onDelete(conv.conversation_id)
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 rounded text-slate-600 hover:text-red-400 transition-all"
                  aria-label={`Delete ${conv.title}`}
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </button>
          </motion.div>
        ))}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-white/[0.05]">
        <p className="text-[10px] text-slate-600 text-center">
          {conversations.length} conversation{conversations.length !== 1 ? "s" : ""}
        </p>
      </div>
    </div>
  )
}
