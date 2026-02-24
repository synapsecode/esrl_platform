"use client"

import { useState, useEffect } from "react"
import toast from "react-hot-toast"
import { useRouter } from "next/navigation"
import { joinApiUrl } from "../../lib/api"

export default function ChatPage() {
    const [pdfUploaded, setPdfUploaded] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [docId, setDocId] = useState()
    const router = useRouter()

    const handleFileUpload = async (file) => {
        if (!file) return
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            toast.error("Please upload a PDF file.")
            return
        }

        setUploading(true)
        const formData = new FormData()
        formData.append("file", file)

        try {
            const response = await fetch(joinApiUrl("/upload_pdf"), {
                method: "POST",
                body: formData,
            })

            const data = await response.json()
            if (response.ok && data.message === "PDF processed" && data.document_id) {
                toast.success("PDF processed", {
                    duration: 2000,
                })
                setDocId(data.document_id)
                setPdfUploaded(true)
            } else {
                const detail = data?.detail || data?.error || "Error trying to process PDF. Try again."
                toast.error(detail, {
                    duration: 3500,
                })
            }
        } catch (e) {
            toast.error("Error trying to process PDF. Try again.", {
                duration: 15000,
            })
        }
        setUploading(false)
    }

    useEffect(() => {
        if (pdfUploaded && docId) {
            router.push(`/chat/${encodeURIComponent(docId)}`)
        }
    }, [docId, pdfUploaded, router])

    return (
        <main className="flex flex-col h-screen bg-black text-white">
            <Navbar />

            {!pdfUploaded && <UploadSection uploading={uploading} onUpload={handleFileUpload} />}
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

function UploadSection({ uploading, onUpload }) {
    const [dragActive, setDragActive] = useState(false)

    const handleDrop = (e) => {
        e.preventDefault()
        setDragActive(false)

        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            onUpload(e.dataTransfer.files[0])
        }
    }

    return (
        <div className="flex flex-1 items-center justify-center">
            <div
                onDragOver={(e) => {
                    e.preventDefault()
                    setDragActive(true)
                }}
                onDragLeave={() => setDragActive(false)}
                onDrop={handleDrop}
                className={`w-125 bg-zinc-800/40 border-2 border-dashed rounded-2xl p-10 text-center transition
        ${dragActive ? "border-white bg-zinc-900" : "border-zinc-700"}`}
            >
                <p className="text-xl font-medium mb-4">Upload your PDF to start chatting</p>

                <p className="text-zinc-400 mb-6 text-sm">Drag & drop your file here or browse</p>

                <label className="cursor-pointer bg-white text-black px-6 py-3 rounded-full text-sm font-medium hover:opacity-90 transition">
                    {uploading ? "Uploading..." : "Browse PDF"}
                    <input type="file" accept=".pdf" hidden onChange={(e) => e.target.files && onUpload(e.target.files[0])} />
                </label>
            </div>
        </div>
    )
}
