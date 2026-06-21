"use client"

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { BarChart, Bar, ResponsiveContainer, XAxis, Tooltip as RechartsTooltip, RadarChart, PolarGrid, PolarAngleAxis, Radar, PolarRadiusAxis } from "recharts"
import { PieChart, Activity, ShieldAlert } from "lucide-react"

const coverageData = [
  { name: 'Covered', value: 42, fill: 'hsl(var(--status-success))' },
  { name: 'Partial', value: 15, fill: 'hsl(var(--status-warning))' },
  { name: 'Missing', value: 8, fill: 'hsl(var(--status-danger))' },
]

const radarData = [
  { subject: 'KYC', A: 90, fullMark: 100 },
  { subject: 'Reporting', A: 75, fullMark: 100 },
  { subject: 'Risk Assessment', A: 60, fullMark: 100 },
  { subject: 'Training', A: 85, fullMark: 100 },
  { subject: 'CDD', A: 95, fullMark: 100 },
]

export function ComplianceDashboard() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-slate-900/40 border-slate-800">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-400 mb-1">Overall Compliance Score</p>
              <h2 className="text-3xl font-bold text-white">82<span className="text-lg text-slate-500">/100</span></h2>
            </div>
            <div className="w-12 h-12 rounded-full bg-primary/20 flex items-center justify-center text-primary">
              <Activity className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-slate-900/40 border-slate-800">
          <CardContent className="p-6 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-400 mb-1">Total Obligations</p>
              <h2 className="text-3xl font-bold text-white">65</h2>
            </div>
            <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-400">
              <ShieldAlert className="w-6 h-6" />
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="bg-slate-900/40 border-slate-800 flex-grow pt-4">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2 text-slate-300">
            <PieChart className="w-4 h-4" /> Coverage Distribution
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={coverageData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <RechartsTooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b' }} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-slate-900/40 border-slate-800 pt-4 hidden md:block">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-slate-300">Regulatory Category Breakdown</CardTitle>
        </CardHeader>
        <CardContent>
           <div className="h-[200px]">
           <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="70%" data={radarData}>
                <PolarGrid stroke="#334155" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                <Radar name="Score" dataKey="A" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
              </RadarChart>
            </ResponsiveContainer>
           </div>
        </CardContent>
      </Card>
    </div>
  )
}
