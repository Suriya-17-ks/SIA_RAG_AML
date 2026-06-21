"use client"

import { useState, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Upload, FileText, X, AlertCircle, CheckCircle2, AlertTriangle, Loader2, ShieldAlert, Activity, ChevronDown, ChevronUp } from "lucide-react"

interface GapResult {
  id: number
  obligation: string
  jurisdiction: string
  status: "COVERED" | "PARTIAL" | "MISSING"
  confidence: number
  evidence: string
  policyRef: string
}

const MOCK_RESULTS: GapResult[] = [
  {
    id: 1,
    obligation: "Customer Identification Program (CIP) — verification of identity for all new accounts",
    jurisdiction: "RBI KYC MD — Para 15",
    status: "COVERED",
    confidence: 0.96,
    evidence: "Section 2.1 of the policy mandates identity verification using Aadhaar or passport for all retail and corporate onboarding.",
    policyRef: "Sec 2.1: Client Onboarding",
  },
  {
    id: 2,
    obligation: "Suspicious Transaction Report (STR) filing within 7 working days of suspicion formation",
    jurisdiction: "PMLA Section 12A",
    status: "PARTIAL",
    confidence: 0.88,
    evidence: "Policy references STR filing but states '30 business days', conflicting with the statutory 7 working day requirement.",
    policyRef: "Sec 4.5: Incident Handling",
  },
  {
    id: 3,
    obligation: "Enhanced Due Diligence (EDD) for Politically Exposed Persons including foreign PEPs",
    jurisdiction: "FATF Recommendation 12",
    status: "MISSING",
    confidence: 0.99,
    evidence: "No mention of PEP categorisation, enhanced monitoring, or senior management approval in the uploaded policy.",
    policyRef: "Not detected",
  },
  {
    id: 4,
    obligation: "Record retention for transaction records: minimum 5 years from account closure",
    jurisdiction: "PMLA Section 12",
    status: "COVERED",
    confidence: 0.94,
    evidence: "Section 7.0 mandates 7-year retention of all transaction records, exceeding the statutory minimum.",
    policyRef: "Sec 7.0: Data Retention",
  },
  {
    id: 5,
    obligation: "Cash Transaction Report (CTR) for transactions exceeding ₹10 lakh in a single day",
    jurisdiction: "RBI KYC MD — Para 41",
    status: "PARTIAL",
    confidence: 0.91,
    evidence: "Policy mentions 'large cash transactions' without specifying the ₹10 lakh threshold explicitly.",
    policyRef: "Sec 5.2: Transaction Monitoring",
  },
  {
    id: 6,
    obligation: "AML staff training programme — minimum annual frequency",
    jurisdiction: "FATF Recommendation 18",
    status: "COVERED",
    confidence: 0.97,
    evidence: "Mandatory bi-annual AML training with documented completion records required per Section 9.1.",
    policyRef: "Sec 9.1: Training & Awareness",
  },
]

const STATUS_CONFIG = {
  COVERED: {
    label:   "Covered",
    icon:    CheckCircle2,
    badgeCls: "badge-covered",
    rowCls:  "hover:bg-emerald-500/[0.03]",
  },
  PARTIAL: {
    label:   "Partial",
    icon:    AlertTriangle,
    badgeCls: "badge-partial",
    rowCls:  "hover:bg-amber-500/[0.03]",
  },
  MISSING: {
    label:   "Missing",
    icon:    AlertCircle,
    badgeCls: "badge-missing",
    rowCls:  "hover:bg-red-500/[0.03]",
  },
}

function StatCard({ label, value, cls }: { label: string; value: string; cls?: string }) {
  return (
    <div className="glass-card rounded-xl p-4 flex items-center justify-between">
      <div>
        <p className="text-xs text-slate-400 font-medium mb-1">{label}</p>
        <p className={`text-2xl font-bold text-white ${cls ?? ""}`}>{value}</p>
      </div>
      <Activity className="w-5 h-5 text-slate-600" />
    </div>
  )
}

function ResultRow({ row, delay }: { row: GapResult; delay: number }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STATUS_CONFIG[row.status]
  const Icon = cfg.icon

  return (
    <>
      <motion.tr
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.3 }}
        className={`border-b border-slate-800/60 transition-colors cursor-pointer ${cfg.rowCls}`}
        onClick={() => setExpanded((v) => !v)}
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((v) => !v)}
        aria-expanded={expanded}
      >
        <td className="px-4 py-4">
          <p className="text-sm font-medium text-slate-200 leading-snug">{row.obligation}</p>
          <p className="text-xs text-slate-500 mt-1">{row.jurisdiction}</p>
        </td>
        <td className="px-4 py-4 text-center">
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${cfg.badgeCls}`}>
            <Icon className="w-3 h-3" />
            {cfg.label}
          </span>
        </td>
        <td className="px-4 py-4 text-center">
          <div className="flex flex-col items-center gap-1">
            <span className="text-sm font-semibold text-white">
              {(row.confidence * 100).toFixed(0)}%
            </span>
            <div className="w-16 h-1 rounded-full bg-slate-800 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  row.status === "COVERED" ? "bg-emerald-500" : row.status === "PARTIAL" ? "bg-amber-500" : "bg-red-500"
                }`}
                style={{ width: `${row.confidence * 100}%` }}
              />
            </div>
          </div>
        </td>
        <td className="px-4 py-4 text-center">
          {expanded ? <ChevronUp className="w-4 h-4 text-slate-500 mx-auto" /> : <ChevronDown className="w-4 h-4 text-slate-500 mx-auto" />}
        </td>
      </motion.tr>
      <AnimatePresence>
        {expanded && (
          <motion.tr
            key="expanded"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <td colSpan={4} className="px-4 pb-4 pt-0">
              <div className="ml-2 p-4 rounded-xl bg-slate-900/60 border border-slate-700/40">
                <p className="text-xs text-slate-400 uppercase tracking-widest font-medium mb-2">Evidence</p>
                <p className="text-sm text-slate-300 leading-relaxed italic">"{row.evidence}"</p>
                <p className="text-xs text-blue-400 mt-2 font-medium">→ {row.policyRef}</p>
              </div>
            </td>
          </motion.tr>
        )}
      </AnimatePresence>
    </>
  )
}

export function GapAnalysisPanel() {
  const [file, setFile]         = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [results, setResults]   = useState<GapResult[] | null>(null)
  const inputRef                = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.type === "application/pdf") setFile(f)
  }

  const handleAnalyze = async () => {
    if (!file) return
    setAnalyzing(true)
    await new Promise((r) => setTimeout(r, 2400))
    setResults(MOCK_RESULTS)
    setAnalyzing(false)
  }

  const covered = results?.filter((r) => r.status === "COVERED").length ?? 0
  const partial  = results?.filter((r) => r.status === "PARTIAL").length ?? 0
  const missing  = results?.filter((r) => r.status === "MISSING").length ?? 0
  const total    = results?.length ?? 0
  const score    = total ? Math.round((covered / total) * 100) : 0

  return (
    <div className="space-y-6">
      {/* Upload area */}
      {!results && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`glass-card rounded-2xl p-10 flex flex-col items-center justify-center gap-4 border-2 border-dashed transition-all duration-300 cursor-pointer ${
            dragging ? "border-blue-500/60 bg-blue-500/[0.06]" : "border-slate-700/60 hover:border-slate-500/60"
          }`}
          role="button"
          aria-label="Upload policy PDF"
          tabIndex={0}
          onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) setFile(f)
            }}
            aria-label="Policy PDF file input"
          />
          <div className="w-14 h-14 rounded-2xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
            <Upload className="w-6 h-6 text-blue-400" />
          </div>
          {file ? (
            <div className="flex items-center gap-2 text-slate-300">
              <FileText className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium">{file.name}</span>
              <button
                onClick={(e) => { e.stopPropagation(); setFile(null) }}
                className="text-slate-500 hover:text-white transition-colors"
                aria-label="Remove file"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <>
              <p className="text-sm font-medium text-slate-300">Drop your AML policy PDF here</p>
              <p className="text-xs text-slate-500">or click to browse · PDF only</p>
            </>
          )}
        </div>
      )}

      {/* Analyze button */}
      {!results && (
        <button
          onClick={handleAnalyze}
          disabled={!file || analyzing}
          className="w-full btn-primary-glow justify-center disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label="Start compliance analysis"
        >
          {analyzing ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Analyzing compliance gaps…
            </>
          ) : (
            <>
              <ShieldAlert className="w-4 h-4" />
              Analyze Compliance
            </>
          )}
        </button>
      )}

      {/* Results */}
      {results && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-6"
        >
          {/* Stats row */}
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Analysis Results</h3>
            <button
              onClick={() => { setResults(null); setFile(null) }}
              className="text-sm text-slate-400 hover:text-white transition-colors"
            >
              ← Upload new
            </button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="glass-card rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-blue-400">{score}%</p>
              <p className="text-xs text-slate-400 mt-1">Compliance Score</p>
            </div>
            <div className="glass-card rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-emerald-400">{covered}</p>
              <p className="text-xs text-slate-400 mt-1">Covered</p>
            </div>
            <div className="glass-card rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-amber-400">{partial}</p>
              <p className="text-xs text-slate-400 mt-1">Partial</p>
            </div>
            <div className="glass-card rounded-xl p-4 text-center">
              <p className="text-3xl font-bold text-red-400">{missing}</p>
              <p className="text-xs text-slate-400 mt-1">Missing</p>
            </div>
          </div>

          {/* Progress bar */}
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span>Overall compliance coverage</span>
              <span>{score}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-800 overflow-hidden flex gap-0.5">
              <div className="h-full bg-emerald-500 rounded-full transition-all duration-1000" style={{ width: `${(covered/total)*100}%` }} />
              <div className="h-full bg-amber-500 rounded-full transition-all duration-1000" style={{ width: `${(partial/total)*100}%` }} />
              <div className="h-full bg-red-500 rounded-full transition-all duration-1000" style={{ width: `${(missing/total)*100}%` }} />
            </div>
            <div className="mt-2 flex gap-4 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" /> Covered</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-500 inline-block" /> Partial</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> Missing</span>
            </div>
          </div>

          {/* Table */}
          <div className="glass-card rounded-2xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full" role="table" aria-label="Compliance gap analysis results">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Regulatory Obligation</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</th>
                    <th className="text-center px-4 py-3 text-xs font-semibold text-slate-400 uppercase tracking-wider">Confidence</th>
                    <th className="px-4 py-3 w-10" />
                  </tr>
                </thead>
                <tbody>
                  {results.map((row, i) => (
                    <ResultRow key={row.id} row={row} delay={i * 0.07} />
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  )
}
