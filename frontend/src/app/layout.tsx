import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { cn } from '@/lib/utils'
import { Navbar } from '@/components/ui/Navbar'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'SIA-RAG | AI-Powered AML Compliance Intelligence',
  description: 'Automated regulatory analysis and policy gap detection using hybrid retrieval and deterministic AI reasoning.',
  keywords: ['AML', 'compliance', 'RAG', 'AI', 'KYC', 'regulatory', 'gap analysis'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={cn(
          "min-h-screen bg-background text-foreground font-sans antialiased overflow-x-hidden selection:bg-blue-600/25 selection:text-blue-200",
          inter.variable
        )}
      >
        <Navbar />
        <div className="pt-16">
          {children}
        </div>
      </body>
    </html>
  )
}
