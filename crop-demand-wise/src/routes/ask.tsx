import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Send } from "lucide-react";
import { askKhetiSetu } from "@/lib/khetiService";
import type { SourceRef } from "@/lib/mockData";
import { SUGGESTED_QUESTIONS } from "@/lib/mockData";
import { DemoDataBadge, Disclaimer, SourceList } from "@/components/kheti/primitives";
import { Logo } from "@/components/kheti/Logo";

export const Route = createFileRoute("/ask")({
  head: () => ({
    meta: [
      { title: "Ask KhetiSetu | Crop recommendation assistant" },
      {
        name: "description",
        content: "Ask why a crop was recommended, how rainfall changes the ranking, and what inputs it needs.",
      },
      { property: "og:title", content: "Ask KhetiSetu" },
      { property: "og:description", content: "A farmer-friendly assistant for your crop recommendation." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Ask,
});

interface Msg {
  id: number;
  role: "user" | "assistant";
  text: string;
  sources?: SourceRef[];
}

function Ask() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: 0,
      role: "assistant",
      text: "Namaste! I can explain your crop recommendation — why a crop was ranked first, what changes if rainfall drops, or what inputs a crop needs. Ask me anything below.",
    },
  ]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const idRef = useRef(1);

  function send(question: string) {
    const q = question.trim();
    if (!q || thinking) return;
    const userMsg: Msg = { id: idRef.current++, role: "user", text: q };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setThinking(true);
    window.setTimeout(() => {
      const res = askKhetiSetu(q);
      setMessages((m) => [
        ...m,
        { id: idRef.current++, role: "assistant", text: res.answer, sources: res.sources },
      ]);
      setThinking(false);
    }, 700);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">Ask KhetiSetu</h1>
          <p className="mt-2 text-muted-foreground">Ask about your crop recommendation.</p>
        </div>
        <DemoDataBadge label="Demo assistant" />
      </div>

      <div className="surface-card mt-6 flex flex-col">
        <ul className="space-y-5 p-4 md:p-6">
          {messages.map((m) =>
            m.role === "user" ? (
              <li key={m.id} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-sm font-medium text-primary-foreground">
                  {m.text}
                </p>
              </li>
            ) : (
              <li key={m.id} className="flex gap-3">
                <span className="mt-1 hidden shrink-0 sm:block">
                  <Logo className="h-7" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed text-foreground">{m.text}</p>
                  {m.sources && (
                    <div className="mt-3">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Sources used
                      </p>
                      <SourceList sources={m.sources} />
                    </div>
                  )}
                </div>
              </li>
            ),
          )}
          {thinking && (
            <li className="text-sm font-medium text-muted-foreground" role="status">
              KhetiSetu is checking your recommendation…
            </li>
          )}
        </ul>

        <div className="border-t border-border p-4 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Suggested questions</p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  onClick={() => send(q)}
                  className="rounded-full border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="mt-4 flex items-end gap-2"
          >
            <label htmlFor="ask-input" className="sr-only">
              Your question
            </label>
            <input
              id="ask-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your question…"
              className="min-w-0 flex-1 rounded-lg border border-border bg-input px-4 py-3 text-base text-foreground outline-none focus:border-primary"
            />
            <button
              type="submit"
              disabled={!input.trim() || thinking}
              className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary-dark disabled:bg-muted disabled:text-muted-foreground"
              aria-label="Send question"
            >
              <Send className="h-5 w-5" aria-hidden />
            </button>
          </form>
        </div>
      </div>

      <div className="mt-4">
        <Disclaimer>
          This assistant is a frontend demo with pre-written answers. It does not call a language model and
          does not guarantee outcomes.
        </Disclaimer>
      </div>
    </div>
  );
}
