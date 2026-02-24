"use client"

import { useState, useRef, useEffect } from "react"
import toast from "react-hot-toast"
import { useRouter } from "next/navigation"

export default function ChatPage() {
    const [pdfUploaded, setPdfUploaded] = useState(false)
    const [uploading, setUploading] = useState(false)
    const [messages, setMessages] = useState([])
    const [input, setInput] = useState("")
    const [docId, setDocId] = useState()
    const bottomRef = useRef(null)
    const router = useRouter()

    const handleFileUpload = async (file) => {
        setUploading(true)
        const api_uri = process.env.NEXT_PUBLIC_API_URI
        const formData = new FormData()
        formData.append("file", file)

        try {
            const response = await fetch(`${api_uri}/upload_pdf`, {
                method: "POST",
                body: formData,
            })

            const data = await response.json()

            console.log(data)

            if (data.message === "PDF processed") {
                toast.success("PDF processed", {
                    duration: 2000,
                })
                setDocId(data.document_id)
                setPdfUploaded(true)
            } else {
                toast.error("Error trying to process PDF. Try again.", {
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

    const sendMessage = async () => {
        if (!input.trim()) return

        const userMsg = { role: "user", content: input }
        setMessages((prev) => [...prev, userMsg])
        setInput("")

        // 🔥 Replace with your chat endpoint
        setTimeout(() => {
            setMessages((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: "Connected to your PDF. This is a sample response.",
                },
            ])
        }, 700)
    }

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    useEffect(() => {
      if(pdfUploaded && docId){
        setTimeout(()=>{}, 1500)
        router.push(`/chat/${docId}`)
      }
    }, [docId])

    return (
        <main className="flex flex-col h-screen bg-black text-white">
            <Navbar />

            {!pdfUploaded ? (
                <UploadSection uploading={uploading} onUpload={handleFileUpload} />
            ) : (
                <>
                    {/* <ChatWindow messages={messages} />
                    <ChatInput input={input} setInput={setInput} sendMessage={sendMessage} /> */}
                </>
            )}

            <div ref={bottomRef} />
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

function ChatWindow({ messages }) {
    return (
        <div className="flex-1 overflow-y-auto px-6 py-8 space-y-6 max-w-3xl mx-auto w-full">
            {messages.length === 0 && <div className="text-center text-zinc-500 mt-32 text-xl">Ask anything about your uploaded PDF.</div>}

            {messages.map((msg, index) => (
                <div key={index} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                    <div
                        className={`px-5 py-3 rounded-2xl max-w-[75%] text-sm leading-relaxed ${
                            msg.role === "user" ? "bg-white text-black" : "bg-zinc-900 text-white border border-zinc-800"
                        }`}
                    >
                        {msg.content}
                    </div>
                </div>
            ))}
        </div>
    )
}

function ChatInput({ input, setInput, sendMessage }) {
    return (
        <div className="border-t border-zinc-800 p-4 bg-black">
            <div className="max-w-3xl mx-auto flex gap-3">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                    placeholder="Ask about your PDF..."
                    className="flex-1 bg-zinc-900 border border-zinc-800 rounded-full px-5 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-white"
                />
                <button onClick={sendMessage} className="bg-white text-black px-6 rounded-full text-sm font-medium hover:opacity-90 transition">
                    Send
                </button>
            </div>
        </div>
    )
}
