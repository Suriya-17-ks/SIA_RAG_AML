"use client"

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { motion } from "framer-motion"
import { AlertCircle, CheckCircle2, AlertTriangle, ExternalLink } from "lucide-react"

// Example placeholder data for compliance results
const results = [
  {
    id: 1,
    obligation: "Customer Identification Program (CIP) requirements for individuals",
    status: "Covered",
    confidence: 0.96,
    citation: "USA PATRIOT Act Section 326",
    policyRef: "Section 2.1: Client Onboarding"
  },
  {
    id: 2,
    obligation: "Suspicious Activity Report (SAR) filing timeframe limits (30 days)",
    status: "Partial",
    confidence: 0.88,
    citation: "BSAA 31 U.S.C. 5318(g)",
    policyRef: "Section 4.5: Incident Handling"
  },
  {
    id: 3,
    obligation: "Enhanced Due Diligence (EDD) procedures for PEPs",
    status: "Missing",
    confidence: 0.99,
    citation: "FATF Recommendation 12",
    policyRef: "None detected"
  },
  {
    id: 4,
    obligation: "Record keeping duration requirements (5 years minimum)",
    status: "Covered",
    confidence: 0.94,
    citation: "PMLA Section 12",
    policyRef: "Section 7.0: Data Retention"
  }
]

export function GapAnalysisTable() {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case "Covered": return <CheckCircle2 className="w-4 h-4 mr-1 text-status-success" />
      case "Partial": return <AlertTriangle className="w-4 h-4 mr-1 text-status-warning" />
      case "Missing": return <AlertCircle className="w-4 h-4 mr-1 text-status-danger" />
      default: return null
    }
  }

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "Covered": return "success"
      case "Partial": return "warning"
      case "Missing": return "destructive"
      default: return "default"
    }
  }

  return (
    <Card className="h-full bg-slate-900/40 border-slate-800 flex flex-col">
      <CardHeader>
        <CardTitle className="text-lg">Compliance Analysis Results</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 overflow-auto">
        <div className="rounded-md border border-slate-800 overflow-hidden">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 bg-slate-800/80 uppercase">
              <tr>
                <th className="px-4 py-3 font-medium">Regulatory Obligation</th>
                <th className="px-4 py-3 font-medium text-center">Status</th>
                <th className="px-4 py-3 font-medium text-center">Confidence</th>
                <th className="px-4 py-3 font-medium">Citation Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {results.map((row, i) => (
                <motion.tr 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  key={row.id} 
                  className="bg-slate-900/20 hover:bg-slate-800/40 transition-colors"
                >
                  <td className="px-4 py-4 font-medium text-slate-200">
                    {row.obligation}
                    <div className="text-xs text-slate-500 font-normal mt-1 flex items-center">
                      Mapped Policy: {row.policyRef}
                    </div>
                  </td>
                  <td className="px-4 py-4 text-center">
                    <Badge variant={getStatusVariant(row.status) as "success" | "warning" | "destructive" | "default"} className="inline-flex w-[90px] justify-center">
                      {getStatusIcon(row.status)}
                      {row.status}
                    </Badge>
                  </td>
                  <td className="px-4 py-4 text-center">
                    <div className="inline-flex items-center text-slate-300">
                      {(row.confidence * 100).toFixed(0)}%
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="flex items-center text-blue-400 hover:text-blue-300 cursor-pointer">
                      <span className="truncate max-w-[150px] mr-1">{row.citation}</span>
                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                    </div>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  )
}
