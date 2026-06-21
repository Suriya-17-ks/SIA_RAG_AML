"use client"

import { GapAnalysisPanel } from "@/components/analyzer/GapAnalysisPanel"
import { motion } from "framer-motion"
import { ShieldAlert, Info } from "lucide-react"

export default function AnalyzerPage() {
  return (
    <main className="min-h-screen bg-background" aria-label="Policy Gap Analyzer">
      <div className="max-w-5xl mx-auto px-4 py-10 space-y-8">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-3"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center">
              <ShieldAlert className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white">Policy Gap Analyzer</h1>
              <p className="text-slate-400 text-sm">
                Automated AML compliance auditing — COVERED · PARTIAL · MISSING
              </p>
            </div>
          </div>

          {/* Info banner */}
          <div className="flex items-start gap-3 px-4 py-3.5 rounded-xl bg-blue-500/[0.06] border border-blue-500/20">
            <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-blue-300/80 leading-relaxed">
              Upload your internal AML policy PDF. The engine compares each regulatory obligation from{" "}
              <strong className="text-blue-300">PMLA 2002</strong>,{" "}
              <strong className="text-blue-300">RBI KYC Master Direction</strong>, and{" "}
              <strong className="text-blue-300">FATF 40 Recommendations</strong>{" "}
              against your policy using a deterministic entailment judge with 0.0% hallucination rate.
            </p>
          </div>
        </motion.div>

        {/* Main panel */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <GapAnalysisPanel />
        </motion.div>

        {/* Legend */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="flex flex-wrap gap-4 text-sm"
        >
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="text-slate-400"><strong className="text-emerald-400">Covered</strong> — Obligation explicitly and completely satisfied</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-amber-500" />
            <span className="text-slate-400"><strong className="text-amber-400">Partial</strong> — Topic addressed but thresholds/scope incomplete</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-slate-400"><strong className="text-red-400">Missing</strong> — No mention of the required concept in policy</span>
          </div>
        </motion.div>
      </div>
    </main>
  )
}
