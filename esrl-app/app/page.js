"use client"

import { useRouter } from "next/navigation";

export default function Home() {

  
  return (
    <main className="min-h-screen bg-black text-white">
      <Navbar />
      <Hero />
    </main>
  );
}

function Navbar() {
  return (
    <nav className="flex items-center justify-between px-8 py-6">
      <button className="bg-zinc-800 text-sm px-4 py-2 rounded-full hover:bg-zinc-700 transition">
        eSRL
      </button>

      <div className="flex items-center gap-8 text-sm text-zinc-400">
        <a href="/chat" className="hover:text-white transition">Upload PDF</a>
        <a className="hover:text-white transition">Summary</a>
        <a href="/chat" className="hover:text-white transition">Chat</a>
      </div>
    </nav>
  );
}

function Hero() {
  const router = useRouter()
  return (
    <section className="flex flex-col items-center justify-center text-center px-6 pt-32">
      <h1 className="text-5xl md:text-6xl font-semibold tracking-tight">
        AI Chat for Study.
      </h1>

      <h2 className="text-4xl md:text-5xl font-semibold text-zinc-500 mt-4">
        Upload and chat about your PDFs.
      </h2>

      <div className="flex gap-4 mt-10">
        <button className="bg-white text-black px-6 py-3 rounded-full font-medium hover:opacity-90 transition" onClick={()=>{router.push("/chat")}}>
          Upload PDF
        </button>

        <button className="bg-zinc-800 px-6 py-3 rounded-full font-medium hover:bg-zinc-700 transition" onClick={()=>{router.push("/how-to-use")}}>
          How it works
        </button>
      </div>

      <div className="mt-32 max-w-3xl">
        <h3 className="text-3xl md:text-4xl font-semibold leading-tight">
          Upload your educational PDF to
          <br />
          get started and discover insights.
        </h3>

        <p className="text-zinc-500 text-2xl mt-4">
          Our AI summarizes, creates quick notes,
          <br />
          and answers your questions in real time.
        </p>
      </div>
    </section>
  );
}
