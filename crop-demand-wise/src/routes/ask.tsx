import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Send } from "lucide-react";
import { Trans, useTranslation } from "react-i18next";

import { ApiError, hasApiToken } from "@/services/api";
import type { RagSourceRef } from "@/services/api";
import { useRagQueryMutation } from "@/services/queries";
import { useFarm } from "@/lib/farm-store";
import { SUGGESTED_QUESTIONS } from "@/lib/constants";
import { Disclaimer, ErrorState, SourceList, UnverifiedBadge } from "@/components/kheti/primitives";
import { Logo } from "@/components/kheti/Logo";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/ask")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("ask.meta.title") },
        { name: "description", content: t("ask.meta.description") },
        { property: "og:title", content: t("ask.meta.ogTitle") },
        { property: "og:description", content: t("ask.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: Ask,
});

interface Msg {
  id: number;
  role: "user" | "assistant";
  /** Null for the intro, whose text is read from the active language instead. */
  text: string | null;
  sources?: RagSourceRef[];
  usedPlaceholderData?: boolean;
}

const INTRO: Msg = { id: 0, role: "assistant", text: null };

function Ask() {
  const { t } = useTranslation();
  const { farmer, recommendation } = useFarm();
  const [messages, setMessages] = useState<Msg[]>([INTRO]);
  const [input, setInput] = useState("");
  const idRef = useRef(1);
  const ragQuery = useRagQueryMutation();

  const districtId = recommendation?.district.id ?? farmer.districtId;

  function send(question: string) {
    const trimmed = question.trim();
    if (!trimmed || ragQuery.isPending) return;

    setMessages((prev) => [...prev, { id: idRef.current++, role: "user", text: trimmed }]);
    setInput("");

    ragQuery.mutate(
      { mode: "ask", question: trimmed, district_id: districtId },
      {
        onSuccess: (result) => {
          setMessages((prev) => [
            ...prev,
            {
              id: idRef.current++,
              role: "assistant",
              text: result.answer,
              sources: result.sources,
              usedPlaceholderData: result.used_placeholder_data,
            },
          ]);
        },
      },
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">{t("ask.title")}</h1>
        <p className="mt-2 text-muted-foreground">{t("ask.subtitle")}</p>
      </div>

      {!hasApiToken && (
        <div className="mt-6 rounded-lg border border-warning/40 bg-warning/5 p-4">
          <p className="text-sm font-semibold text-foreground">{t("ask.tokenNoticeTitle")}</p>
          <p className="mt-2 text-sm text-muted-foreground">
            <Trans
              i18nKey="ask.tokenNoticeDetail"
              components={{
                code: <code className="rounded bg-muted px-1 py-0.5 text-xs" />,
                path: <code className="text-xs" />,
              }}
            />
          </p>
        </div>
      )}

      <div className="surface-card mt-6 flex flex-col">
        <ul className="space-y-5 p-4 md:p-6">
          {messages.map((message) =>
            message.role === "user" ? (
              <li key={message.id} className="flex justify-end">
                <p className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-4 py-3 text-sm font-medium text-primary-foreground">
                  {message.text}
                </p>
              </li>
            ) : (
              <li key={message.id} className="flex gap-3">
                <span className="mt-1 hidden shrink-0 sm:block">
                  <Logo className="h-7" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm leading-relaxed text-foreground">
                    {message.text ?? t("ask.intro")}
                  </p>
                  {message.usedPlaceholderData && (
                    <div className="mt-2">
                      <UnverifiedBadge label={t("ask.unverifiedGuidance")} />
                    </div>
                  )}
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-3">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        {t("sources.used")}
                      </p>
                      <SourceList
                        sources={message.sources.map((source) => ({
                          id: source.source_id,
                          title:
                            source.organization ?? t("sources.fallback", { id: source.source_id }),
                          detail: null,
                        }))}
                      />
                    </div>
                  )}
                </div>
              </li>
            ),
          )}
          {ragQuery.isPending && (
            <li className="text-sm font-medium text-muted-foreground" role="status">
              {t("ask.searching")}
            </li>
          )}
          {ragQuery.isError && (
            <li>
              <ErrorState
                error={
                  ragQuery.error instanceof ApiError
                    ? ragQuery.error
                    : new Error(t("ask.unreachable"))
                }
                onRetry={() => ragQuery.reset()}
              />
            </li>
          )}
        </ul>

        <div className="border-t border-border p-4 md:p-6">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {t("ask.suggestedHeading")}
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {SUGGESTED_QUESTIONS.map(({ labelKey, question }) => (
              <li key={labelKey}>
                <button
                  type="button"
                  onClick={() => send(question)}
                  disabled={ragQuery.isPending}
                  className="rounded-full border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:text-muted-foreground"
                >
                  {t(labelKey)}
                </button>
              </li>
            ))}
          </ul>

          <form
            onSubmit={(event) => {
              event.preventDefault();
              send(input);
            }}
            className="mt-4 flex items-end gap-2"
          >
            <label htmlFor="ask-input" className="sr-only">
              {t("ask.inputLabel")}
            </label>
            <input
              id="ask-input"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={t("ask.inputPlaceholder")}
              className="min-w-0 flex-1 rounded-lg border border-border bg-input px-4 py-3 text-base text-foreground outline-none focus:border-primary"
            />
            <button
              type="submit"
              disabled={!input.trim() || ragQuery.isPending}
              className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary-dark disabled:bg-muted disabled:text-muted-foreground"
              aria-label={t("ask.send")}
            >
              <Send className="h-5 w-5" aria-hidden />
            </button>
          </form>
        </div>
      </div>

      <div className="mt-4">
        <Disclaimer>{t("ask.disclaimer")}</Disclaimer>
      </div>
    </div>
  );
}
