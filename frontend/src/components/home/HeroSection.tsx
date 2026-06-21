"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import Link from "next/link"
import { ArrowRight, ShieldCheck, Sparkles, ChevronRight } from "lucide-react"

const prompts = [
  "What is the STR filing timeline under RBI guidelines?",
  "What are KYC requirements for high-risk customers?",
  "What is the cash transaction reporting threshold under PMLA?",
  "What EDD measures are required for PEPs?",
]

const metrics = [
  { label: "Retrieval Hit@1",   value: "60.4%", delta: "+163%" },
  { label: "Gap Classification", value: "F1 1.00", delta: "Perfect" },
  { label: "Hallucination Rate", value: "0.0%",   delta: "Eliminated" },
]

export function HeroSection() {
  const [activePrompt, setActivePrompt] = useState(0)

  return (
    <section
      className="relative z-10 flex flex-col items-center justify-center min-h-[88vh] text-center px-4 pt-8 pb-24"
      aria-label="Hero section"
    >
      {/* Badge */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="inline-flex items-center rounded-full border border-blue-500/25 bg-blue-500/10 px-4 py-1.5 text-sm font-medium text-blue-300 mb-8 backdrop-blur-sm"
      >
        <ShieldCheck className="mr-2 h-3.5 w-3.5" />
        AML Compliance · Powered by Hybrid RAG + LLaMA 3.3 70B
      </motion.div>

      {/* Headline */}
      <motion.h1
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.1 }}
        className="text-5xl md:text-7xl font-bold tracking-tight text-white max-w-5xl leading-[1.08]"
      >
        Intelligent AML
        <br />
        <span className="text-gradient">Compliance Automation</span>
      </motion.h1>

      {/* Subtitle */}
      <motion.p
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.2 }}
        className="mt-6 text-lg md:text-xl text-slate-400 max-w-2xl leading-relaxed"
      >
        Automated regulatory analysis and policy gap detection using hybrid dense+sparse retrieval
        and deterministic AI reasoning — with <span className="text-white font-medium">0% hallucination</span>.
      </motion.p>

      {/* CTAs */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
        className="mt-10 flex flex-col sm:flex-row items-center gap-3"
      >
        <Link href="/assistant">
          <button className="btn-primary-glow group" aria-label="Try Regulatory Assistant">
            <Sparkles className="w-4 h-4" />
            Try Regulatory Assistant
            <ArrowRight className="w-4 h-4 ml-1 transition-transform group-hover:translate-x-1" />
          </button>
        </Link>
        <Link href="/analyzer">
          <button
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm text-slate-300 border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] hover:text-white transition-all duration-200"
            aria-label="Run Gap Analysis"
          >
            Run Gap Analysis
            <ChevronRight className="w-4 h-4" />
          </button>
        </Link>
      </motion.div>

      {/* Live demo prompt strip */}
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, delay: 0.45 }}
        className="mt-14 w-full max-w-2xl"
      >
        <p className="text-xs text-slate-500 uppercase tracking-widest mb-3 font-medium">
          Example regulatory queries
        </p>
        <div className="glass rounded-2xl p-1.5 flex flex-col gap-1.5">
          {prompts.map((prompt, i) => (
            <button
              key={i}
              onClick={() => setActivePrompt(i)}
              className={`text-left px-4 py-3 rounded-xl text-sm transition-all duration-200 flex items-center gap-3 ${
                activePrompt === i
                  ? "bg-blue-600/20 text-blue-200 border border-blue-500/30"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/[0.03]"
              }`}
              aria-pressed={activePrompt === i}
            >
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${activePrompt === i ? "bg-blue-400" : "bg-slate-600"}`} />
              {prompt}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Metric pills */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.6 }}
        className="mt-12 flex flex-wrap justify-center gap-4"
      >
        {metrics.map((m, i) => (
          <div
            key={i}
            className="flex items-center gap-3 px-5 py-3 glass rounded-xl"
          >
            <div className="text-left">
              <p className="text-xs text-slate-500 font-medium">{m.label}</p>
              <p className="text-white font-bold text-lg leading-none mt-0.5">{m.value}</p>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 text-xs font-semibold border border-emerald-500/20">
              {m.delta}
            </span>
          </div>
        ))}
      </motion.div>
    </section>
  )
}
