"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { Answer } from "@/components/Answer";
import { SourceDetail, SourceList } from "@/components/SourcePanel";
import { Button, ErrorNotice, LockIcon } from "@/components/ui";
import { api, errorMessage, json, request } from "@/lib/api";
import { timeAgo } from "@/lib/format";
import { readEvents } from "@/lib/sse";
import type { Citation, Conversation, ConversationDetail, Message, ModelProfile } from "@/lib/types";

const SUGGESTIONS = [
  "What is our remote work policy?",
  "How do I fix error E104 on the MW-400 press?",
  "Summarize the travel reimbursement rules.",
  "What are the salary bands for engineers?",
  "Compare the 2025 and 2026 procurement approval limits.",
];

interface Pending {
  question: string;
  content: string;
  stage: "retrieving" | "generating";
  sources?: { count: number; profile: string; external: boolean };
}

export function ChatView({ conversationId: initialId }: { conversationId?: string }) {
  const [conversationId, setConversationId] = useState(initialId);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [profiles, setProfiles] = useState<ModelProfile[]>([]);
  const [profile, setProfile] = useState<string>("");
  const [input, setInput] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Citation | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  const loadConversations = useCallback(() => {
    api<Conversation[]>("/conversations").then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    loadConversations();
    api<ModelProfile[]>("/model-profiles")
      .then((all) => {
        const enabled = all.filter((p) => p.enabled);
        setProfiles(enabled);
        setProfile((enabled.find((p) => p.is_default) ?? enabled[0])?.name ?? "");
      })
      .catch((e) => setError(errorMessage(e)));
  }, [loadConversations]);

  useEffect(() => {
    if (!initialId) return;
    api<ConversationDetail>(`/conversations/${initialId}`)
      .then((c) => setMessages(c.messages))
      .catch((e) => setError(errorMessage(e)));
  }, [initialId]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, pending?.content]);

  async function send(question: string) {
    question = question.trim();
    if (!question || pending) return;
    setError(null);
    setSelected(null);
    setInput("");
    setPending({ question, content: "", stage: "retrieving" });
    try {
      let id = conversationId;
      if (!id) {
        id = (await api<Conversation>("/conversations", { method: "POST", body: json({}) })).id;
        setConversationId(id);
        // Update the URL without remounting the page mid-stream.
        window.history.replaceState(null, "", `/app/chat/${id}`);
      }
      const response = await request(`/conversations/${id}/messages`, {
        method: "POST",
        body: json({ message: question, model_profile: profile || undefined }),
      });
      for await (const { event, data } of readEvents(response)) {
        if (event === "sources") {
          setPending((p) => p && { ...p, stage: "generating", sources: data as Pending["sources"] });
        } else if (event === "delta") {
          const text = (data as { text: string }).text;
          setPending((p) => p && { ...p, content: p.content + text });
        } else if (event === "error") {
          setError((data as { message: string }).message);
        } else if (event === "done") {
          const answer = data as Message;
          const now = new Date().toISOString();
          setMessages((m) => [
            ...m,
            { ...answer, id: `q-${answer.id}`, role: "user", content: question, citations: [], created_at: now },
            answer,
          ]);
        }
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(null);
      loadConversations();
    }
  }

  const current = profiles.find((p) => p.name === profile);

  return (
    <div className="flex h-[calc(100vh-7.5rem)] lg:h-screen">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border xl:flex">
        <div className="p-3">
          <Link href="/app/chat" className="block">
            <Button variant="secondary" className="w-full">
              New conversation
            </Button>
          </Link>
        </div>
        <ul className="flex-1 space-y-0.5 overflow-y-auto px-3 pb-3">
          {conversations.map((c) => (
            <li key={c.id}>
              <Link
                href={`/app/chat/${c.id}`}
                className={`block rounded-lg px-3 py-2 text-sm ${
                  c.id === conversationId ? "bg-surface-2 font-medium" : "text-muted hover:bg-surface-2 hover:text-text"
                }`}
              >
                <div className="truncate">{c.title}</div>
                <div className="text-xs text-muted">{timeAgo(c.updated_at)}</div>
              </Link>
            </li>
          ))}
        </ul>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
            {messages.length === 0 && !pending && <Welcome onPick={send} />}

            <div className="space-y-8">
              {messages.map((m) =>
                m.role === "user" ? (
                  <UserBubble key={m.id} text={m.content} />
                ) : (
                  <AssistantMessage key={m.id} message={m} selected={selected} onCite={setSelected} />
                ),
              )}
              {pending && (
                <>
                  <UserBubble text={pending.question} />
                  <div>
                    <ProgressLine pending={pending} />
                    {pending.content && (
                      <div className="mt-2">
                        <Answer content={pending.content} citations={[]} onCite={() => {}} />
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            {error && (
              <div className="mt-6">
                <ErrorNotice message={error} />
              </div>
            )}
            <div ref={bottom} />
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="border-t border-border bg-surface/80 px-4 py-3 backdrop-blur sm:px-6"
        >
          <div className="mx-auto max-w-3xl">
            <div className="flex items-end gap-2 rounded-xl border border-border bg-surface p-2 focus-within:border-accent">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send(input);
                  }
                }}
                rows={1}
                maxLength={4000}
                placeholder="Ask about policies, manuals, procedures…"
                className="max-h-40 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
              />
              <Button type="submit" disabled={!input.trim() || !!pending}>
                {pending ? "Answering…" : "Ask"}
              </Button>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
              <label className="flex items-center gap-1.5">
                Model
                <select
                  value={profile}
                  onChange={(e) => setProfile(e.target.value)}
                  className="rounded-md border border-border bg-surface px-1.5 py-0.5 text-xs text-text"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.name}>
                      {p.name} ({p.model})
                    </option>
                  ))}
                </select>
              </label>
              {current && <EgressNote profile={current} />}
            </div>
          </div>
        </form>
      </div>

      {selected && (
        <aside className="fixed inset-x-3 bottom-3 z-10 max-h-[60vh] overflow-y-auto lg:static lg:inset-auto lg:max-h-none lg:w-80 lg:shrink-0 lg:border-l lg:border-border lg:p-4">
          <SourceDetail citation={selected} onClose={() => setSelected(null)} />
        </aside>
      )}
    </div>
  );
}

function EgressNote({ profile }: { profile: ModelProfile }) {
  return profile.max_classification === "confidential" ? (
    <span className="flex items-center gap-1">
      <span className="h-1.5 w-1.5 rounded-full bg-secret" />
      {profile.external ? "External API, allowed confidential data" : "Runs on your infrastructure, can use confidential spaces"}
    </span>
  ) : (
    <span className="flex items-center gap-1">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      {profile.external ? "External API: confidential spaces are never sent" : "Searches internal spaces only"}
    </span>
  );
}

function Welcome({ onPick }: { onPick: (q: string) => void }) {
  return (
    <div className="py-10 text-center">
      <h1 className="text-2xl font-semibold">What do you need to know?</h1>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">
        Answers come only from documents you&apos;re allowed to read, with a source for every statement.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPick(s)}
            className="rounded-full border border-border bg-surface px-3.5 py-1.5 text-sm transition hover:border-accent"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm text-white dark:text-bg">
        {text}
      </div>
    </div>
  );
}

function ProgressLine({ pending }: { pending: Pending }) {
  return (
    <div className="flex items-center gap-2 text-xs text-muted">
      <span className="h-2 w-2 animate-pulse rounded-full bg-accent" />
      {pending.stage === "retrieving"
        ? "Searching documents you can access…"
        : `Found ${pending.sources?.count ?? 0} passages · writing with ${pending.sources?.profile}`}
    </div>
  );
}

function AssistantMessage({
  message,
  selected,
  onCite,
}: {
  message: Message;
  selected: Citation | null;
  onCite: (c: Citation) => void;
}) {
  return (
    <div>
      {message.status !== "complete" && (
        <div className="mb-2 text-xs text-warn">
          {message.status === "partial" ? "Answer interrupted before it finished." : "The answer failed."}
        </div>
      )}
      <Answer content={message.content} citations={message.citations} onCite={onCite} selected={selected} />
      <SourceList citations={message.citations} selected={selected} onSelect={onCite} />
      <div className="mt-2 flex flex-wrap items-center gap-x-3 text-xs text-muted">
        {message.model && <span>{message.model}</span>}
        {message.latency_ms !== null && <span>{(message.latency_ms / 1000).toFixed(1)}s</span>}
        {message.input_tokens > 0 && (
          <span>
            {message.input_tokens.toLocaleString()} in / {message.output_tokens.toLocaleString()} out tokens
          </span>
        )}
        {message.citations.some((c) => c.restricted) && (
          <span className="flex items-center gap-1">
            <LockIcon /> Some sources are no longer accessible to you
          </span>
        )}
      </div>
    </div>
  );
}
