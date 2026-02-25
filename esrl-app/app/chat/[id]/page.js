"use client"

import { Send } from "lucide-react"
import { useParams } from "next/navigation"
import { useState, useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import { getApiBase } from "../../../lib/api"

export default function DocumentPage() {
    const [leftWidth, setLeftWidth] = useState(25)
    const [rightWidth, setRightWidth] = useState(20)
    const [showVideo, setShowVideo] = useState(false)
    const [summary, setSummary] = useState(null)
    const [notes, setNotes] = useState(null)
    const [video, setVideo] = useState(null)
    const [summaryLoading, setSummaryLoading] = useState(true)
    const [notesLoading, setNotesLoading] = useState(true)
    const [videoLoading, setVideoLoading] = useState(true)
    const [videoError, setVideoError] = useState("")
    const [error, setError] = useState("")
    const [gameTaskId, setGameTaskId] = useState("")
    const [gameStatus, setGameStatus] = useState("idle")
    const [gamePhase, setGamePhase] = useState("")
    const [gameError, setGameError] = useState("")
    const [gameLaunching, setGameLaunching] = useState(false)
    const hasAutoLaunched = useRef(false)
    const initializedDocRef = useRef("")
    const insightsTimerRef = useRef(null)

    const routeDocId = useParams().id
    const rawDocId = Array.isArray(routeDocId) ? routeDocId[0] : routeDocId || ""
    const docId = (() => {
        try {
            return decodeURIComponent(rawDocId)
        } catch {
            return rawDocId
        }
    })()
    const apiBase = getApiBase()

    const isDragging = useRef(null)

    const startDrag = (panel) => {
        isDragging.current = panel
    }

    const stopDrag = () => {
        isDragging.current = null
    }

    const onDrag = (e) => {
        if (!isDragging.current) return

        const screenWidth = window.innerWidth
        const percent = (e.clientX / screenWidth) * 100

        if (isDragging.current === "left") {
            setLeftWidth(Math.min(Math.max(percent, 15), 40))
        }

        if (isDragging.current === "right") {
            const rightPercent = 100 - percent
            setRightWidth(Math.min(Math.max(rightPercent, 15), 35))
        }
    }

    useEffect(() => {
        window.addEventListener("mousemove", onDrag)
        window.addEventListener("mouseup", stopDrag)
        return () => {
            window.removeEventListener("mousemove", onDrag)
            window.removeEventListener("mouseup", stopDrag)
        }
    }, [])

    useEffect(() => {
        if (!docId || initializedDocRef.current === docId) return
        initializedDocRef.current = docId

        const fetchData = async () => {
            const encodedDocId = encodeURIComponent(docId)
            setError("")
            setSummaryLoading(true)
            setNotesLoading(true)
            setVideoLoading(true)
            setVideoError("")
            setGameError("")
            setGameTaskId("")
            setGameStatus("queued")
            setGamePhase("Initializing game pipeline...")
            hasAutoLaunched.current = false

            const videoPromise = fetch(`${apiBase}/generate_video/${encodedDocId}`, {
                method: "POST",
            })
                .then((res) => {
                    if (!res.ok) throw new Error("Video request failed")
                    return res.json()
                })
                .then((data) => {
                    if (data?.error) {
                        setVideoError(data.error)
                    }
                    setVideo(data)
                })
                .catch((err) => {
                    console.error("Video request failed:", err)
                    setVideoError("Video generation failed.")
                })
                .finally(() => {
                    setVideoLoading(false)
                })

            const gamePromise = fetch(`${apiBase}/game/generate/${encodedDocId}`, {
                method: "POST",
            })
                .then((res) => {
                    if (!res.ok) throw new Error("Game generation request failed")
                    return res.json()
                })
                .then((data) => {
                    if (!data.task_id) {
                        throw new Error("No game task id returned by backend.")
                    }
                    setGameTaskId(data.task_id)
                    setGameStatus(data.status || "queued")
                    setGamePhase("Game Design (1/3)")
                })
                .catch((err) => {
                    console.error("Game generation request failed:", err)
                    setGameStatus("failed")
                    setGameError("Could not start game generation.")
                })

            // Prioritize generator startup, then load insight panes.
            if (insightsTimerRef.current) clearTimeout(insightsTimerRef.current)
            insightsTimerRef.current = setTimeout(() => {
                fetch(`${apiBase}/notes/summary`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ document_id: docId }),
                })
                    .then((res) => {
                        if (!res.ok) throw new Error("Summary request failed")
                        return res.json()
                    })
                    .then((data) => {
                        setSummary(data)
                    })
                    .catch((err) => {
                        console.error("Summary request failed:", err)
                        setError("Could not load document insights. Please try again.")
                    })
                    .finally(() => {
                        setSummaryLoading(false)
                    })

                fetch(`${apiBase}/notes`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ document_id: docId }),
                })
                    .then((res) => {
                        if (!res.ok) throw new Error("Notes request failed")
                        return res.json()
                    })
                    .then((data) => {
                        setNotes(data)
                    })
                    .catch((err) => {
                        console.error("Notes request failed:", err)
                        setError("Could not load document insights. Please try again.")
                    })
                    .finally(() => {
                        setNotesLoading(false)
                    })
            }, 250)

            await Promise.allSettled([videoPromise, gamePromise])
        }

        fetchData()

        return () => {
            if (insightsTimerRef.current) {
                clearTimeout(insightsTimerRef.current)
                insightsTimerRef.current = null
            }
        }
    }, [apiBase, docId])

    useEffect(() => {
        if (!gameTaskId) return

        let intervalId = null

        const pollStatus = async () => {
            try {
                const response = await fetch(`${apiBase}/game/status/${gameTaskId}`)
                if (!response.ok) {
                    throw new Error("Could not fetch game status")
                }
                const data = await response.json()
                setGameStatus(data.status || "queued")
                setGamePhase(data.phase || "")

                if (data.status === "failed") {
                    setGameError(data.error || "Game generation failed.")
                }

                if (data.status === "completed" && !hasAutoLaunched.current) {
                    hasAutoLaunched.current = true
                    setGameLaunching(true)
                    try {
                        const launchResponse = await fetch(`${apiBase}/game/launch/${gameTaskId}`, {
                            method: "POST",
                        })
                        const launchData = await launchResponse.json()
                        if (!launchResponse.ok) {
                            throw new Error(launchData?.error || "Game launch failed.")
                        }
                    } catch (err) {
                        console.error("Game launch failed:", err)
                        setGameError("Game generated, but auto-launch failed. Try Launch Game.")
                    } finally {
                        setGameLaunching(false)
                    }
                }
            } catch (err) {
                console.error("Game status poll failed:", err)
            }
        }

        pollStatus()
        intervalId = setInterval(pollStatus, 4000)

        return () => {
            if (intervalId) clearInterval(intervalId)
        }
    }, [apiBase, gameTaskId])

    const videoUrl = buildMediaUrl(video?.video_path, apiBase)

    return (
        <main className="h-screen flex flex-col bg-black text-white">
            <Navbar docId={docId} />

            <div className="flex-1 flex overflow-hidden">
                {/* LEFT PANEL */}
                <div style={{ width: `${leftWidth}%` }} className="bg-zinc-900/40 border-r border-zinc-800 flex flex-col">
                    <LeftPanel
                        summary={summary}
                        notes={notes}
                        summaryLoading={summaryLoading}
                        notesLoading={notesLoading}
                        error={error}
                    />
                </div>

                {/* DRAG HANDLE */}
                <div onMouseDown={() => startDrag("left")} className="w-1 bg-zinc-900/40 cursor-col-resize hover:bg-zinc-600 transition" />

                {/* CHAT PANEL */}
                <div className="flex-1 bg-black flex flex-col">
                    <ChatPanel apiBase={apiBase} documentId={docId} />
                </div>

                {/* DRAG HANDLE */}
                <div onMouseDown={() => startDrag("right")} className="w-1 bg-zinc-900/40 cursor-col-resize hover:bg-zinc-600 transition" />

                {/* RIGHT PANEL */}
                <div style={{ width: `${rightWidth}%` }} className="bg-zinc-900/40 border-l border-zinc-800 p-6">
                    <div className="h-full flex flex-col gap-6">
                        <GameSection
                            status={gameStatus}
                            phase={gamePhase}
                            error={gameError}
                            taskId={gameTaskId}
                            launching={gameLaunching}
                            onLaunch={async () => {
                                if (!gameTaskId) return
                                setGameLaunching(true)
                                setGameError("")
                                try {
                                    const response = await fetch(`${apiBase}/game/launch/${gameTaskId}`, {
                                        method: "POST",
                                    })
                                    const data = await response.json()
                                    if (!response.ok) {
                                        throw new Error(data?.error || "Game launch failed.")
                                    }
                                } catch (err) {
                                    setGameError(err.message || "Game launch failed.")
                                } finally {
                                    setGameLaunching(false)
                                }
                            }}
                        />
                        <VideoSection
                            video_url={videoUrl}
                            loading={videoLoading}
                            error={videoError}
                            onOpen={() => setShowVideo(true)}
                        />
                    </div>
                </div>
            </div>

            {showVideo && <VideoModal video_url={videoUrl} onClose={() => setShowVideo(false)} />}
        </main>
    )
}

function buildMediaUrl(path, apiBase) {
    if (!path) return ""
    if (path.startsWith("http://") || path.startsWith("https://")) return path

    const normalizedBase = apiBase.endsWith("/") ? apiBase.slice(0, -1) : apiBase
    const normalizedPath = path.startsWith("/") ? path : `/${path}`
    return `${normalizedBase}${normalizedPath}`
}

function Navbar({ docId }) {
    const label = docId
        ? `${docId.slice(0, 3)}...${docId.slice(-3)}`
        : "loading..."

    return (
        <nav className="flex items-center justify-between px-8 py-6">
            <button className="bg-zinc-800 text-sm px-4 py-2 rounded-full hover:bg-zinc-700 transition">eSRL</button>

            <div className="flex items-center justify-between gap-8">
                <div className="flex items-center gap-8 text-sm text-zinc-400">
                    <a href="/chat" className="hover:text-white transition">
                        Upload PDF
                    </a>
                </div>
                <span className=" transition text-sm text-green-600">eSRL Doc: {label}</span>
            </div>
        </nav>
    )
}

function LeftPanel({ summary, notes, summaryLoading, notesLoading, error }) {
    const [summaryOpen, setSummaryOpen] = useState(true)
    const [notesOpen, setNotesOpen] = useState(true)
    const [showNotesOverlay, setShowNotesOverlay] = useState(false)
    const [showFlashcardAnswers, setShowFlashcardAnswers] = useState(true)
    const [showMcqAnswers, setShowMcqAnswers] = useState(true)

    const renderMarkdown = (text) => (
        <div className="prose prose-invert max-w-none text-sm">
            <ReactMarkdown
                components={{
                    h1: ({ children }) => <h1 className="text-xl font-semibold text-white">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-lg font-semibold text-white">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-base font-semibold text-white">{children}</h3>,
                    p: ({ children }) => <p className="text-sm text-zinc-200 leading-relaxed">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-5 text-sm text-zinc-200 space-y-1">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-5 text-sm text-zinc-200 space-y-1">{children}</ol>,
                    li: ({ children }) => <li>{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                    em: ({ children }) => <em className="text-zinc-200 italic">{children}</em>,
                    a: ({ children, href }) => (
                        <a href={href} className="text-blue-300 hover:text-blue-200 underline" target="_blank" rel="noreferrer">
                            {children}
                        </a>
                    ),
                    blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-zinc-600 pl-3 text-zinc-300 italic">{children}</blockquote>
                    ),
                    code: ({ children }) => (
                        <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-zinc-200">{children}</code>
                    ),
                }}
            >
                {text}
            </ReactMarkdown>
        </div>
    )

    const parsePossibleJson = (text) => {
        const trimmed = text.trim()
        const jsonBlockMatch = trimmed.match(/^```json\s*([\s\S]*?)\s*```$/i)
        const jsonString = jsonBlockMatch ? jsonBlockMatch[1] : trimmed

        if (!jsonString.startsWith("{") || !jsonString.endsWith("}")) {
            return null
        }

        try {
            return JSON.parse(jsonString)
        } catch (err) {
            return null
        }
    }

    const renderNotesObject = (value, options = {}) => {
        const {
            showFlashcardAnswers: showFlashcards = true,
            showMcqAnswers: showAnswers = true,
        } = options
        const sections = []

        if (Array.isArray(value.flashcards) && value.flashcards.length > 0) {
            sections.push(
                <div key="flashcards">
                    <h4 className="text-sm font-semibold text-white mb-2">Flashcards</h4>
                    <div className="space-y-3">
                        {value.flashcards.map((card, index) => (
                            <div key={`flashcard-${index}`} className="rounded-lg border border-zinc-800 bg-black/30 p-3">
                                <p className="text-xs text-zinc-400">Q{index + 1}</p>
                                <p className="text-sm text-zinc-100 mt-1">{card.question}</p>
                                {showFlashcards ? (
                                    <>
                                        <p className="text-xs text-zinc-400 mt-2">Answer</p>
                                        <p className="text-sm text-zinc-200 mt-1">{card.answer}</p>
                                    </>
                                ) : (
                                    <p className="text-xs text-zinc-500 mt-2">Answer hidden</p>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )
        }

        if (typeof value.cheat_sheet === "string" && value.cheat_sheet.trim()) {
            sections.push(
                <div key="cheat_sheet">
                    <h4 className="text-sm font-semibold text-white mb-2">Cheat Sheet</h4>
                    {renderMarkdown(value.cheat_sheet)}
                </div>
            )
        }

        if (Array.isArray(value.mcqs) && value.mcqs.length > 0) {
            sections.push(
                <div key="mcqs">
                    <h4 className="text-sm font-semibold text-white mb-2">MCQs</h4>
                    <div className="space-y-3">
                        {value.mcqs.map((mcq, index) => (
                            <div key={`mcq-${index}`} className="rounded-lg border border-zinc-800 bg-black/30 p-3">
                                <p className="text-xs text-zinc-400">Q{index + 1}</p>
                                <p className="text-sm text-zinc-100 mt-1">{mcq.question}</p>
                                {Array.isArray(mcq.options) && mcq.options.length > 0 && (
                                    <ul className="mt-2 text-sm text-zinc-200 space-y-1">
                                        {mcq.options.map((option, optionIndex) => (
                                            <li key={`mcq-${index}-opt-${optionIndex}`}>{option}</li>
                                        ))}
                                    </ul>
                                )}
                                {showAnswers && mcq.answer && (
                                    <p className="text-xs text-zinc-400 mt-2">Answer: {mcq.answer}</p>
                                )}
                                {!showAnswers && <p className="text-xs text-zinc-500 mt-2">Answer hidden</p>}
                            </div>
                        ))}
                    </div>
                </div>
            )
        }

        if (Array.isArray(value.interview_questions) && value.interview_questions.length > 0) {
            sections.push(
                <div key="interview_questions">
                    <h4 className="text-sm font-semibold text-white mb-2">Interview Questions</h4>
                    <ul className="list-disc pl-5 text-sm text-zinc-200 space-y-1">
                        {value.interview_questions.map((question, index) => (
                            <li key={`interview-${index}`}>{question}</li>
                        ))}
                    </ul>
                </div>
            )
        }

        if (sections.length > 0) {
            return <div className="space-y-4">{sections}</div>
        }

        return null
    }

    const renderContent = (value) => {
        if (value === null || value === undefined) return null

        if (typeof value === "string") {
            const parsed = parsePossibleJson(value)
            if (parsed) return renderContent(parsed)
            return renderMarkdown(value)
        }

        if (Array.isArray(value)) {
            return (
                <ul className="text-zinc-300 text-sm space-y-2">
                    {value.map((item, index) => (
                        <li key={`${index}-${JSON.stringify(item).slice(0, 8)}`}>• {typeof item === "string" ? item : JSON.stringify(item)}</li>
                    ))}
                </ul>
            )
        }

        if (typeof value === "object") {
            const notesView = renderNotesObject(value)
            if (notesView) return notesView

            if (typeof value.summary === "string") {
                return renderMarkdown(value.summary)
            }

            if (typeof value.notes === "string") {
                const parsedNotes = parsePossibleJson(value.notes)
                if (parsedNotes) {
                    const parsedView = renderNotesObject(parsedNotes)
                    if (parsedView) return parsedView
                }
                return renderMarkdown(value.notes)
            }

            return <pre className="text-zinc-300 text-xs leading-relaxed whitespace-pre-wrap">{JSON.stringify(value, null, 2)}</pre>
        }

        return <p className="text-zinc-300 text-sm leading-relaxed">{String(value)}</p>
    }

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <Collapsible title="Summary" open={summaryOpen} setOpen={setSummaryOpen}>
                {summaryLoading && <p className="text-zinc-400 text-sm">Loading summary...</p>}
                {!summaryLoading && error && <p className="text-red-400 text-sm">{error}</p>}
                {!summaryLoading && !error && renderContent(summary)}
            </Collapsible>

            <Collapsible
                title="Quick Notes"
                open={notesOpen}
                setOpen={setNotesOpen}
                onHeaderClick={() => setShowNotesOverlay(true)}
            >
                {notesLoading && <p className="text-zinc-400 text-sm">Loading notes...</p>}
                {!notesLoading && error && <p className="text-red-400 text-sm">{error}</p>}
                {!notesLoading && !error && (
                    <button
                        onClick={() => setShowNotesOverlay(true)}
                        className="mt-2 text-xs bg-zinc-800 text-zinc-200 px-3 py-2 rounded-md hover:bg-zinc-700 transition"
                    >
                        Open Quick Notes
                    </button>
                )}
            </Collapsible>

            <QuickNotesOverlay
                isOpen={showNotesOverlay}
                onClose={() => setShowNotesOverlay(false)}
                notes={notes}
                renderNotesObject={renderNotesObject}
                showFlashcardAnswers={showFlashcardAnswers}
                setShowFlashcardAnswers={setShowFlashcardAnswers}
                showMcqAnswers={showMcqAnswers}
                setShowMcqAnswers={setShowMcqAnswers}
            />
        </div>
    )
}

function Collapsible({ title, open, setOpen, children, onHeaderClick }) {
    return (
        <div className="bg-zinc-800/40 border border-zinc-700 rounded-xl">
            <div
                onClick={onHeaderClick || (() => setOpen(!open))}
                className="flex justify-between items-center px-4 py-3 cursor-pointer"
            >
                <h3 className="text-xs uppercase tracking-wider text-zinc-400">{title}</h3>
                <span className="text-zinc-500 text-sm">{open ? "−" : "+"}</span>
            </div>

            {open && <div className="px-4 pb-4">{children}</div>}
        </div>
    )
}

function QuickNotesOverlay({
    isOpen,
    onClose,
    notes,
    renderNotesObject,
    showFlashcardAnswers,
    setShowFlashcardAnswers,
    showMcqAnswers,
    setShowMcqAnswers,
}) {
    if (!isOpen) return null

    const normalizedNotes = (() => {
        if (!notes) return null
        if (notes.notes && typeof notes.notes === "string") {
            const trimmed = notes.notes.trim()
            const jsonBlockMatch = trimmed.match(/^```json\s*([\s\S]*?)\s*```$/i)
            const jsonString = jsonBlockMatch ? jsonBlockMatch[1] : trimmed

            if (jsonString.startsWith("{") && jsonString.endsWith("}")) {
                try {
                    return JSON.parse(jsonString)
                } catch (err) {
                    return notes
                }
            }
        }

        return notes
    })()

    return (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center">
            <div className="w-11/12 max-w-4xl max-h-[85vh] overflow-hidden rounded-2xl border border-zinc-800 bg-zinc-950 shadow-2xl">
                <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800">
                    <div>
                        <h3 className="text-lg font-semibold text-white">Quick Notes</h3>
                        <p className="text-xs text-zinc-400">Toggle sections and answers while you study.</p>
                    </div>
                    <button onClick={onClose} className="text-zinc-300 hover:text-white transition">✕</button>
                </div>

                <div className="flex flex-wrap gap-3 px-6 py-4 border-b border-zinc-800 text-xs text-zinc-300">
                    <button
                        onClick={() => setShowFlashcardAnswers((prev) => !prev)}
                        className="rounded-full border border-zinc-700 px-3 py-1 hover:border-zinc-500 transition"
                    >
                        {showFlashcardAnswers ? "Hide" : "Show"} flashcard answers
                    </button>
                    <button
                        onClick={() => setShowMcqAnswers((prev) => !prev)}
                        className="rounded-full border border-zinc-700 px-3 py-1 hover:border-zinc-500 transition"
                    >
                        {showMcqAnswers ? "Hide" : "Show"} MCQ answers
                    </button>
                </div>

                <div className="p-6 overflow-y-auto max-h-[70vh]">
                    {renderNotesObject(normalizedNotes, {
                        showFlashcardAnswers,
                        showMcqAnswers,
                    }) || <p className="text-sm text-zinc-400">No quick notes available.</p>}
                </div>
            </div>
        </div>
    )
}

function ChatPanel({ apiBase, documentId }) {
    const [messages, setMessages] = useState([{ role: "assistant", content: "Ask me anything about this document." }])
    const [sending, setSending] = useState(false)

    const bottomRef = useRef()

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [messages])

    return (
        <>
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.map((msg, i) => (
                    <ChatBubble key={i} side={msg.role === "user" ? "right" : "left"}>
                        {msg.role === "assistant" ? <AssistantMessage content={msg.content} images={msg.images} /> : msg.content}
                    </ChatBubble>
                ))}

                <div ref={bottomRef} />
            </div>

            <ChatInput
                sending={sending}
                onSend={async (text) => {
                    if (!text.trim() || sending) return

                    const updatedMessages = [...messages, { role: "user", content: text }]
                    setMessages(updatedMessages)
                    setSending(true)

                    try {
                        const response = await fetch(`${apiBase}/chat`, {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json",
                            },
                            body: JSON.stringify({ messages: updatedMessages, document_id: documentId }),
                        })

                        const data = await response.json()
                        const answer = response.ok && data?.answer ? data.answer : "Sorry, I could not get a response."

                        const images = Array.isArray(data?.images)
                            ? data.images.map((image) => ({
                                  ...image,
                                  url: buildMediaUrl(image.url || image.path, apiBase),
                              }))
                            : []

                        setMessages([...updatedMessages, { role: "assistant", content: answer, images }])
                    } catch (err) {
                        console.error("Chat request failed:", err)
                        setMessages([...updatedMessages, { role: "assistant", content: "Sorry, something went wrong." }])
                    } finally {
                        setSending(false)
                    }
                }}
            />
        </>
    )
}

function ChatBubble({ children, side }) {
    const isRight = side === "right"

    return (
        <div className={`flex ${isRight ? "justify-end" : "justify-start"}`}>
            <div
                className={`px-4 py-3 rounded-xl text-sm max-w-md
        ${isRight ? "bg-neutral-800/70 text-white" : "bg-zinc-800 text-zinc-200"}`}
            >
                {children}
            </div>
        </div>
    )
}

function AssistantMessage({ content, images }) {
    return (
        <div className="space-y-4">
            <div className="prose prose-invert max-w-none text-sm">
                <ReactMarkdown
                    components={{
                        h1: ({ children }) => <h1 className="text-xl font-semibold text-white">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-lg font-semibold text-white">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-base font-semibold text-white">{children}</h3>,
                        p: ({ children }) => <p className="text-sm text-zinc-200 leading-relaxed">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc pl-5 text-sm text-zinc-200 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal pl-5 text-sm text-zinc-200 space-y-1">{children}</ol>,
                        li: ({ children }) => <li>{children}</li>,
                        strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                        em: ({ children }) => <em className="text-zinc-200 italic">{children}</em>,
                        a: ({ children, href }) => (
                            <a href={href} className="text-blue-300 hover:text-blue-200 underline" target="_blank" rel="noreferrer">
                                {children}
                            </a>
                        ),
                        blockquote: ({ children }) => (
                            <blockquote className="border-l-2 border-zinc-600 pl-3 text-zinc-300 italic">{children}</blockquote>
                        ),
                        code: ({ children }) => (
                            <code className="rounded bg-zinc-900 px-1 py-0.5 text-xs text-zinc-200">{children}</code>
                        ),
                    }}
                >
                    {content}
                </ReactMarkdown>
            </div>

            {Array.isArray(images) && images.length > 0 && (
                <div className="grid gap-3">
                    {images.map((image, index) => (
                        <div key={`${image.url}-${index}`} className="rounded-lg border border-zinc-700 bg-black/40 p-3">
                            {image.url && (
                                <img src={image.url} alt={image.caption || "Document image"} className="w-full rounded-md" />
                            )}
                            {image.caption && <p className="mt-2 text-xs text-zinc-300">{image.caption}</p>}
                            {image.context && <p className="mt-1 text-xs text-zinc-500">{image.context}</p>}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

function ChatInput({ onSend, sending }) {
    const [input, setInput] = useState("")

    const send = () => {
        if (!input.trim()) return
        onSend(input)
        setInput("")
    }

    return (
        <div className="p-4 bg-black">
            <div className="flex gap-3">
                <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && send()}
                    placeholder="Ask something..."
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-zinc-600"
                />

                <button
                    onClick={send}
                    className="bg-zinc-800 text-zinc-200 px-4 py-3 rounded-xl text-sm font-medium hover:opacity-90 transition disabled:opacity-50"
                    disabled={sending}
                >
                    <Send />
                </button>
            </div>
        </div>
    )
}

function VideoSection({ video_url, loading, error, onOpen }) {
    return (
        <div className="h-full flex flex-col justify-between">
            {/* Header */}
            <div>
                <h3 className="text-xs uppercase tracking-wider text-zinc-400 mb-4">Generated Video</h3>

                {/* Video Preview Card */}
                <div
                    onClick={video_url ? onOpen : undefined}
                    className={`relative rounded-xl overflow-hidden border border-zinc-800 transition ${video_url ? "bg-zinc-900/50 hover:bg-zinc-800/60 cursor-pointer group" : "bg-zinc-900/30"}`}
                >
                    {video_url ? (
                        <video src={video_url} className="w-full h-48 object-cover opacity-80 group-hover:opacity-100 transition" />
                    ) : (
                        <div className="w-full h-48 flex items-center justify-center text-xs text-zinc-500">
                            {loading ? "Generating video..." : "Video not available"}
                        </div>
                    )}

                    {/* Play Overlay */}
                    <div className="absolute inset-0 flex items-center justify-center bg-black/30 backdrop-blur-sm opacity-0 group-hover:opacity-100 transition">
                        <div className="w-14 h-14 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                            <div className="w-0 h-0 border-l-10 border-l-black border-y-[6px] border-y-transparent ml-1"></div>
                        </div>
                    </div>
                </div>

                {/* Caption */}
                <p className="text-zinc-500 text-xs mt-3">Click to expand and view the full generated explanation video.</p>
                {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
            </div>

            {/* Fullscreen Button */}
            <button
                onClick={onOpen}
                disabled={!video_url}
                className="mt-6 text-sm bg-zinc-800 text-white py-2 border border-zinc-700 focus:border-zinc-200 rounded-lg hover:opacity-90 transition disabled:opacity-50"
            >
                Play Video
            </button>
        </div>
    )
}

function GameSection({ status, phase, error, taskId, launching, onLaunch }) {
    const statusLabel = status || "idle"
    const isReady = status === "completed"
    const isBusy = ["queued", "generating_design", "generating_levels", "generating_code"].includes(status)

    return (
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <h3 className="text-xs uppercase tracking-wider text-zinc-400">Generated Game</h3>
            <p className="mt-2 text-sm text-zinc-200">
                Status: <span className="text-white">{statusLabel}</span>
            </p>
            {phase && <p className="mt-1 text-xs text-zinc-400">{phase}</p>}
            {taskId && <p className="mt-1 text-[11px] text-zinc-500">Task: {taskId.slice(0, 8)}...</p>}
            {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

            <button
                onClick={onLaunch}
                disabled={!isReady || launching}
                className="mt-4 w-full text-sm bg-zinc-800 text-white py-2 border border-zinc-700 rounded-lg hover:opacity-90 transition disabled:opacity-50"
            >
                {launching ? "Launching..." : "Launch Game"}
            </button>

            {isBusy && <p className="mt-2 text-xs text-zinc-500">Building game from your notes...</p>}
        </div>
    )
}

function VideoModal({ video_url, onClose }) {
    if (!video_url) return null

    return (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="relative w-4/5 max-w-4xl bg-black rounded-2xl overflow-hidden shadow-2xl">
                <button onClick={onClose} className="absolute top-4 right-4 text-white z-10">
                    ✕
                </button>

                <video src={video_url} controls autoPlay className="w-full" />
            </div>
        </div>
    )
}
