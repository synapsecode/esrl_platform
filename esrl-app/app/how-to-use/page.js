"use client"
import { useState, useEffect } from "react"
import { ArrowDown as MoveDown } from "lucide-react"

export default function HowToUsePage() {
    return (
        <main className="min-h-screen bg-black text-white">
            <Navbar />

            {/* Navbar Spacer (assuming navbar fixed at top) */}
            <div className="h-16 bg-black/70 backdrop-blur-md flex items-center px-10">
                <h1 className="text-sm uppercase tracking-wider text-zinc-400">How It Works</h1>
            </div>

            {/* Content */}
            <div className="max-w-5xl mx-auto px-6 pb-20">
                {/* Header */}
                <div className="text-center mb-20">
                    <h2 className="text-4xl font-semibold mb-4">Understand Your Documents, Effortlessly</h2>
                    <p className="text-zinc-400 max-w-2xl mx-auto text-sm leading-relaxed">
                        Upload your PDF and instantly receive structured insights, interactive explanations, and a visual breakdown — all in one focused workspace.
                    </p>
                </div>

                {/* Steps Grid */}
                <div className="grid md:grid-cols-2 gap-8">
                    <StepCard
                        number="01"
                        title="Upload Your PDF"
                        description="Click on “Upload PDF” to begin. Drag and drop your document or browse your device to select a file."
                    />

                    <StepCard
                        number="02"
                        title="Automatic Processing"
                        description="Your document is analyzed securely. We extract structure, key concepts, and visual elements in seconds."
                    />

                    <StepCard
                        number="03"
                        title="Receive Structured Insights"
                        description="Access a clear summary, concise quick notes, and a generated explainer video tailored to your document."
                    />

                    <StepCard
                        number="04"
                        title="Chat with Your Document"
                        description="Ask questions, clarify concepts, and explore topics in depth — your PDF becomes interactive."
                    />
                </div>

                <div className="mt-16 flex justify-center">
                    <ScrollIndicator />
                </div>

                {/* Bottom CTA */}
                <div className="mt-24 text-center">
                    <div className="inline-flex items-center gap-6 bg-zinc-900/50 border border-zinc-800 px-8 py-6 rounded-2xl backdrop-blur-sm">
                        <div>
                            <p className="text-sm text-zinc-400">Ready to get started?</p>
                            <p className="text-lg font-medium">Upload your first PDF now.</p>
                        </div>
                        <a href="/chat" target="_blank" className="bg-white text-black px-6 py-3 rounded-xl text-sm font-medium hover:opacity-90 transition">Upload PDF</a>
                    </div>
                </div>
            </div>
        </main>
    )
}

function Navbar() {
    return (
        <nav className="flex items-center justify-between px-8 py-6">
            <button className="bg-zinc-800 text-sm px-4 py-2 rounded-full hover:bg-zinc-700 transition">eSRL</button>

            <div className="flex items-center gap-8 text-sm text-zinc-400">
                <a href="/chat" className="hover:text-white transition">
                    Upload PDF
                </a>
                <a className="hover:text-white transition">Summary</a>
                <a href="/chat" className="hover:text-white transition">
                    Chat
                </a>
            </div>
        </nav>
    )
}

function ScrollIndicator() {
    const [visible, setVisible] = useState(true)

    useEffect(() => {
        const handleScroll = () => {
            if (window.scrollY > 50) {
                setVisible(false)
            }
        }

        window.addEventListener("scroll", handleScroll)
        return () => window.removeEventListener("scroll", handleScroll)
    }, [])

    if (!visible) return null

    return (
        <div className="flex flex-col items-center scale-75 text-zinc-500 transition-opacity duration-300 rounded-full border px-3 pt-2 animate-bounce">
            <span className="text-xs tracking-wider uppercase mb-0"><MoveDown /> </span>
            <span className="text-xs tracking-wider uppercase -mt-4 mb-3"><MoveDown /> </span>

            {/* <div className="w-6 h-10 border border-zinc-700 rounded-full flex items-start justify-center p-1">
                <div className="w-1 h-2 bg-zinc-500 rounded-full animate-bounce" />
            </div> */}
        </div>
    )
}

function StepCard({ number, title, description }) {
    return (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-2xl p-8 backdrop-blur-sm hover:bg-zinc-900/70 transition">
            <div className="flex items-center justify-between mb-6">
                <span className="text-zinc-600 text-sm font-mono">{number}</span>
            </div>

            <h3 className="text-lg font-medium mb-3">{title}</h3>

            <p className="text-zinc-400 text-sm leading-relaxed">{description}</p>
        </div>
    )
}
