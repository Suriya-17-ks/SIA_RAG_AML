"use client"

import { HeroSection }  from "@/components/home/HeroSection"
import { FeatureCard }  from "@/components/home/FeatureCard"
import { QueryInput }   from "@/components/home/QueryInput"
import dynamic           from "next/dynamic"
import {
  Database, FileSearch, BrainCircuit, ShieldAlert, Zap, GitMerge,
  ArrowRight, BookOpen, Scale
} from "lucide-react"
import Link from "next/link"
import { motion } from "framer-motion"

const ShaderBackground = dynamic(
  () => import("@/components/ui/shader-background"),
  { ssr: false }
)

/* ── Feature data ──────────────────────────────────────────────── */
const features = [
  {
    title: "Hybrid Dense + BM25 Retrieval",
    description:
      "Fuses semantic vector search with exact keyword matching. Catches numeric thresholds like '₹10 lakh' that pure embedding models miss.",
    icon: Database,
    accent: "blue" as const,
    badge: "60.4% Hit@1",
  },
  {
    title: "Cross-Encoder Re-ranking",
    description:
      "Mutual-attention scoring over every (query, chunk) pair surfaces the exact clause first — not buried at position 4.",
    icon: FileSearch,
    accent: "cyan" as const,
  },
  {
    title: "Deterministic Gap Analysis",
    description:
      "Precision-engineered LLM judge with a 3-step entailment checklist: COVERED / PARTIAL / MISSING. Macro F1 = 1.00.",
    icon: BrainCircuit,
    accent: "purple" as const,
    badge: "F1 1.00",
  },
  {
    title: "Hallucination-Free Evidence",
    description:
      "Every cited quote is verified by deterministic substring matching. If it isn't literally in the policy, it's rejected.",
    icon: ShieldAlert,
    accent: "emerald" as const,
    badge: "0.0% halluc.",
  },
  {
    title: "Jurisdiction-Aware Scoring",
    description:
      "PMLA and RBI statutory law outranks FATF recommendations automatically. 80% semantic + 20% authority blending.",
    icon: Scale,
    accent: "blue" as const,
  },
  {
    title: "Reciprocal Rank Fusion",
    description:
      "RRF merges dense and sparse rankings without score calibration — mathematically superior to simple score averaging.",
    icon: GitMerge,
    accent: "cyan" as const,
  },
]

/* ── Regulatory docs ───────────────────────────────────────────── */
const docs = [
  { name: "Prevention of Money Laundering Act 2002", tag: "PMLA", color: "text-blue-400   bg-blue-500/10   border-blue-500/20" },
  { name: "RBI KYC Master Direction 2016",           tag: "RBI",  color: "text-cyan-400   bg-cyan-500/10   border-cyan-500/20" },
  { name: "FATF 40 Recommendations 2012–2022",       tag: "FATF", color: "text-purple-400 bg-purple-500/10 border-purple-500/20" },
]

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden" aria-label="SIA-RAG Home">

      {/* Shader background — lazy-loaded */}
      <ShaderBackground />

      {/* Page content */}
      <div className="relative z-10">

        {/* ── HERO ─────────────────────────────────────────────── */}
        <HeroSection />

        {/* ── FEATURE CARDS ────────────────────────────────────── */}
        <section className="container mx-auto px-4 py-24" aria-labelledby="features-heading">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-14"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-blue-400 mb-3">
              Under the hood
            </p>
            <h2
              id="features-heading"
              className="text-3xl md:text-4xl font-bold text-white mb-4"
            >
              Built beyond ordinary RAG
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto text-base">
              Every component is purpose-engineered for the precision requirements of AML legal compliance.
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 max-w-6xl mx-auto">
            {features.map((f, i) => (
              <FeatureCard key={i} {...f} delay={i * 0.08} />
            ))}
          </div>
        </section>

        {/* ── INTERACTIVE ASSISTANT DEMO ───────────────────────── */}
        <section className="container mx-auto px-4 py-20" aria-labelledby="assistant-heading">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="text-center mb-10"
          >
            <p className="text-xs font-semibold uppercase tracking-widest text-cyan-400 mb-3">
              Live demo
            </p>
            <h2 id="assistant-heading" className="text-3xl md:text-4xl font-bold text-white mb-4">
              Ask anything about AML regulations
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto text-base">
              Get precise, evidence-cited answers sourced directly from PMLA, RBI, and FATF documents.
            </p>
          </motion.div>
          <QueryInput />
          <div className="text-center mt-6">
            <Link
              href="/assistant"
              className="inline-flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              Open full assistant
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </section>

        {/* ── REGULATORY CORPUS ────────────────────────────────── */}
        <section className="container mx-auto px-4 py-20" aria-labelledby="corpus-heading">
          <div className="max-w-4xl mx-auto">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5 }}
              className="glass rounded-3xl p-8 md:p-12"
            >
              <div className="flex items-start gap-4 mb-8">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center flex-shrink-0">
                  <BookOpen className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h2 id="corpus-heading" className="text-xl font-bold text-white mb-1">
                    Regulatory Knowledge Base
                  </h2>
                  <p className="text-slate-400 text-sm">
                    3,848 indexed chunks across 4 ChromaDB collections · ~369 pages · 3 regulatory sources
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {docs.map((doc, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 12 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800"
                  >
                    <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-semibold border mb-3 ${doc.color}`}>
                      {doc.tag}
                    </span>
                    <p className="text-sm font-medium text-slate-200 leading-snug">{doc.name}</p>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          </div>
        </section>

        {/* ── FINAL CTA BANNER ─────────────────────────────────── */}
        <section className="container mx-auto px-4 py-24">
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
            className="max-w-3xl mx-auto text-center"
          >
            <div className="relative glass rounded-3xl p-10 md:p-16 overflow-hidden">
              {/* Background pulse */}
              <div className="absolute inset-0 -z-10">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 rounded-full bg-blue-600/10 blur-3xl" />
              </div>
              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                Ready to automate your compliance audit?
              </h2>
              <p className="text-slate-400 mb-8 text-base">
                Upload your internal AML policy and get a structured gap report in seconds.
              </p>
              <Link href="/analyzer">
                <button className="btn-primary-glow mx-auto">
                  <Zap className="w-4 h-4" />
                  Run Gap Analysis
                  <ArrowRight className="w-4 h-4" />
                </button>
              </Link>
            </div>
          </motion.div>
        </section>

        {/* ── FOOTER ───────────────────────────────────────────── */}
        <footer className="border-t border-white/[0.06] py-8 px-4">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
            <span className="text-slate-500 text-sm">
              SIA-RAG · Amrita School of Engineering, Chennai
            </span>
            <span className="text-slate-600 text-sm">
              Built with LLaMA 3.3 70B · Groq · ChromaDB · LangGraph
            </span>
          </div>
        </footer>
      </div>
    </main>
  )
}
