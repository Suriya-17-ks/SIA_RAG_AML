"use client"

import { motion } from "framer-motion"
import { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"
import { GlowingEffect } from "@/components/ui/glowing-effect"

interface FeatureCardProps {
  title: string
  description: string
  icon: LucideIcon
  delay?: number
  accent?: "blue" | "cyan" | "purple" | "emerald"
  badge?: string
}

const accentMap = {
  blue:    { icon: "text-blue-400",    bg: "bg-blue-500/10",   border: "group-hover:border-blue-500/40" },
  cyan:    { icon: "text-cyan-400",    bg: "bg-cyan-500/10",   border: "group-hover:border-cyan-500/40" },
  purple:  { icon: "text-purple-400",  bg: "bg-purple-500/10", border: "group-hover:border-purple-500/40" },
  emerald: { icon: "text-emerald-400", bg: "bg-emerald-500/10",border: "group-hover:border-emerald-500/40" },
}

export function FeatureCard({
  title,
  description,
  icon: Icon,
  delay = 0,
  accent = "blue",
  badge,
}: FeatureCardProps) {
  const a = accentMap[accent]

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.55, delay, ease: "easeOut" }}
      whileHover={{ y: -4, scale: 1.01 }}
      className="group h-full"
    >
      <div
        className={cn(
          "relative h-full rounded-[1.25rem] border-[0.75px] border-border p-2 md:rounded-[1.5rem] md:p-3",
          a.border
        )}
      >
        {/* Interactive glowing border effect */}
        <GlowingEffect
          spread={40}
          glow={true}
          disabled={false}
          proximity={64}
          inactiveZone={0.01}
          borderWidth={3}
        />

        {/* Card inner content */}
        <div
          className={cn(
            "relative flex h-full flex-col justify-between gap-5 overflow-hidden rounded-xl border-[0.75px] bg-background p-6 shadow-sm dark:shadow-[0px_0px_27px_0px_rgba(45,45,45,0.3)]"
          )}
        >
          {/* Icon */}
          <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center", a.bg)}>
            <Icon className={cn("w-5 h-5", a.icon)} aria-hidden="true" />
          </div>

          {/* Content */}
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-base font-semibold text-white leading-snug">{title}</h3>
              {badge && (
                <span className="flex-shrink-0 px-2 py-0.5 rounded-full bg-blue-500/15 text-blue-300 text-[10px] font-semibold border border-blue-500/20">
                  {badge}
                </span>
              )}
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">{description}</p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
