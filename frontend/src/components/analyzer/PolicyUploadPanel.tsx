"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { UploadCloud, File, FileText, CheckCircle } from "lucide-react"

export function PolicyUploadPanel() {
  const [isDragOver, setIsDragOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  return (
    <Card className="h-full bg-slate-900/40 border-slate-800">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <FileText className="w-5 h-5 text-primary" />
          Internal Policy Upload
        </CardTitle>
      </CardHeader>
      <CardContent>
        {file ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex flex-col items-center justify-center p-8 border border-slate-700 rounded-xl bg-slate-800/50"
          >
            <CheckCircle className="w-12 h-12 text-status-success mb-4" />
            <p className="font-medium text-slate-200">{file.name}</p>
            <p className="text-sm text-slate-400 mb-6">{(file.size / 1024).toFixed(1)} KB</p>
            <Button variant="outline" onClick={() => setFile(null)}>Remove File</Button>
          </motion.div>
        ) : (
          <div
            onDragOver={handleDragOver}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            className={`flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-xl transition-colors cursor-pointer ${
              isDragOver ? "border-primary bg-primary/10" : "border-slate-700 hover:border-slate-500 hover:bg-slate-800/50"
            }`}
          >
            <UploadCloud className={`w-12 h-12 mb-4 ${isDragOver ? "text-primary" : "text-slate-500"}`} />
            <p className="font-medium text-slate-300 mb-2">Drag & Drop policy document</p>
            <p className="text-xs text-slate-500 mb-6">Supports PDF, DOCX, TXT</p>
            
            <label htmlFor="file-upload">
              <span className="inline-flex h-9 items-center justify-center rounded-md bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground shadow-sm hover:bg-secondary/80 cursor-pointer">
                Browse Files
              </span>
              <input
                id="file-upload"
                type="file"
                accept=".pdf,.docx,.txt"
                className="hidden"
                onChange={handleFileChange}
              />
            </label>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
