"use client"

import { useState, useRef, useCallback, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Mic, MicOff, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

interface VoiceInputProps {
  onTranscript: (text: string) => void
  disabled?: boolean
  backendUrl?: string
}

type RecordingState = "idle" | "recording" | "processing"

export function VoiceInput({
  onTranscript,
  disabled = false,
  backendUrl = "http://localhost:8000",
}: VoiceInputProps) {
  const [state, setState]         = useState<RecordingState>("idle")
  const [error, setError]         = useState<string | null>(null)
  const mediaRecorder             = useRef<MediaRecorder | null>(null)
  const chunks                    = useRef<Blob[]>([])
  const [waveform, setWaveform]   = useState<number[]>(Array(5).fill(0.3))
  const animFrame                 = useRef<number>(0)
  const analyserRef               = useRef<AnalyserNode | null>(null)
  const streamRef                 = useRef<MediaStream | null>(null)

  // Animate waveform bars using analyser
  const updateWaveform = useCallback(() => {
    if (!analyserRef.current) return
    const data = new Uint8Array(analyserRef.current.frequencyBinCount)
    analyserRef.current.getByteFrequencyData(data)
    // Sample 5 frequency bands
    const bands = 5
    const step = Math.floor(data.length / bands)
    const bars = Array.from({ length: bands }, (_, i) => {
      const val = data[i * step] / 255
      return Math.max(0.15, val)
    })
    setWaveform(bars)
    animFrame.current = requestAnimationFrame(updateWaveform)
  }, [])

  const startRecording = async () => {
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      // Set up audio analyser for waveform
      const audioCtx = new AudioContext()
      const analyser = audioCtx.createAnalyser()
      analyser.fftSize = 64
      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)
      analyserRef.current = analyser

      // Choose supported MIME type
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4"

      const recorder = new MediaRecorder(stream, { mimeType })
      chunks.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }

      recorder.onstop = async () => {
        // Stop all tracks
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        cancelAnimationFrame(animFrame.current)
        analyserRef.current = null
        setWaveform(Array(5).fill(0.3))

        if (chunks.current.length === 0) {
          setState("idle")
          return
        }

        setState("processing")
        const blob = new Blob(chunks.current, { type: mimeType })

        try {
          const formData = new FormData()
          formData.append("file", blob, `recording.${mimeType.includes("webm") ? "webm" : "mp4"}`)

          const res = await fetch(`${backendUrl}/transcribe/`, {
            method: "POST",
            body: formData,
          })

          if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: "Transcription failed" }))
            throw new Error(err.detail || "Transcription failed")
          }

          const data = await res.json()
          if (data.text) {
            onTranscript(data.text)
          }
        } catch (err: any) {
          setError(err.message || "Failed to transcribe")
        } finally {
          setState("idle")
        }
      }

      mediaRecorder.current = recorder
      recorder.start()
      setState("recording")
      animFrame.current = requestAnimationFrame(updateWaveform)
    } catch (err: any) {
      if (err.name === "NotAllowedError") {
        setError("Microphone access denied")
      } else {
        setError("Could not access microphone")
      }
      setState("idle")
    }
  }

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop()
    }
  }

  const handleClick = () => {
    if (disabled) return
    if (state === "idle") startRecording()
    else if (state === "recording") stopRecording()
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cancelAnimationFrame(animFrame.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  return (
    <div className="relative flex items-center gap-2">
      {/* Waveform bars (visible during recording) */}
      <AnimatePresence>
        {state === "recording" && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: "auto" }}
            exit={{ opacity: 0, width: 0 }}
            className="flex items-center gap-[3px] h-8 px-2"
          >
            {waveform.map((h, i) => (
              <motion.div
                key={i}
                className="w-[3px] rounded-full bg-red-400"
                animate={{ height: `${h * 28}px` }}
                transition={{ duration: 0.08 }}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Label */}
      <AnimatePresence>
        {state === "recording" && (
          <motion.span
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -4 }}
            className="text-xs text-red-400 font-medium whitespace-nowrap"
          >
            Listening…
          </motion.span>
        )}
        {state === "processing" && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-xs text-blue-400 font-medium whitespace-nowrap"
          >
            Transcribing…
          </motion.span>
        )}
      </AnimatePresence>

      {/* Mic button */}
      <button
        onClick={handleClick}
        disabled={disabled || state === "processing"}
        className={cn(
          "relative w-9 h-9 rounded-lg flex items-center justify-center transition-all duration-200 flex-shrink-0",
          state === "idle"
            ? "text-slate-400 hover:text-white hover:bg-white/[0.07] border border-transparent"
            : state === "recording"
            ? "text-red-400 bg-red-500/10 border border-red-500/30"
            : "text-blue-400 bg-blue-500/10 border border-blue-500/30",
          disabled && "opacity-40 cursor-not-allowed"
        )}
        aria-label={
          state === "idle"
            ? "Start voice recording"
            : state === "recording"
            ? "Stop recording"
            : "Processing audio"
        }
      >
        {/* Pulse ring during recording */}
        {state === "recording" && (
          <motion.div
            className="absolute inset-0 rounded-lg border-2 border-red-400"
            animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}

        {state === "processing" ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : state === "recording" ? (
          <MicOff className="w-4 h-4" />
        ) : (
          <Mic className="w-4 h-4" />
        )}
      </button>

      {/* Error tooltip */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute right-0 top-full mt-2 px-3 py-1.5 rounded-lg bg-red-500/15 border border-red-500/30 text-xs text-red-400 whitespace-nowrap z-50"
          >
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
