"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const SUGGESTED = [
  "What are the most common grounds for IPR institution?",
  "How does claim construction differ between IPR and district court?",
  "What is the standard for obviousness under 35 USC 103?",
  "When is a patent claim cancelled vs. amended in PTAB proceedings?",
];

export default function ChatTab() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(question: string) {
    if (!question.trim() || loading) return;
    setError(null);

    const userMsg: Message = { role: "user", content: question.trim(), timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Request failed");
      }

      const assistantMsg: Message = {
        role: "assistant",
        content: data.answer,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setError(msg);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-220px)] min-h-[500px]">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4 pr-1">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
            <div>
              <div className="w-16 h-16 rounded-2xl bg-indigo-700/30 border border-indigo-600/30 flex items-center justify-center text-3xl mx-auto mb-4">
                🏛️
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">Ask PTAB Intelligence</h2>
              <p className="text-sm text-gray-400 max-w-md">
                Ask anything about USPTO patent proceedings, PTAB decisions, obviousness rejections,
                claim construction, or office action strategy.
              </p>
            </div>

            {/* Suggested questions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-2xl">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="text-left text-sm text-gray-300 bg-gray-900 border border-gray-700
                             hover:border-indigo-500 hover:text-white rounded-lg px-4 py-3
                             transition-all duration-150"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-lg bg-indigo-700 flex items-center justify-center text-sm flex-shrink-0 mt-1">
                  🏛️
                </div>
              )}
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-indigo-600 text-white rounded-tr-sm"
                    : "bg-gray-800 text-gray-100 rounded-tl-sm border border-gray-700"
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
                <p className={`text-xs mt-1.5 ${msg.role === "user" ? "text-indigo-200" : "text-gray-500"}`}>
                  {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-lg bg-gray-700 flex items-center justify-center text-sm flex-shrink-0 mt-1">
                  👤
                </div>
              )}
            </div>
          ))
        )}

        {/* Loading bubble */}
        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-8 h-8 rounded-lg bg-indigo-700 flex items-center justify-center text-sm flex-shrink-0">
              🏛️
            </div>
            <div className="bg-gray-800 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex gap-1 items-center h-5">
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" />
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg px-4 py-3">
            ⚠️ {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-gray-800 pt-4">
        <div className="flex gap-3 items-end">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about PTAB proceedings, patents, or rejections…"
            rows={2}
            className="input-field flex-1 resize-none min-h-[60px] max-h-40"
            disabled={loading}
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className="btn-primary h-[60px] px-6 flex items-center gap-2"
          >
            <span>{loading ? "Thinking…" : "Send"}</span>
            {!loading && <span>↑</span>}
          </button>
        </div>
        <p className="text-xs text-gray-600 mt-2">Press Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  );
}
