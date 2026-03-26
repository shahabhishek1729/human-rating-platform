import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../../api";
import type { ChatMessage, DelegationTask } from "../../types";

const DEFAULT_ASSISTANT_MESSAGE: ChatMessage = {
  role: "assistant",
  content:
    "Hello! I'm here to help you with this question. Feel free to ask me anything about the problem, request calculations, or discuss your reasoning.",
};

interface ChatInterfaceProps {
  task: DelegationTask;
  sessionToken: string;
  pid: string;
  experimentId: number;
  onComplete: () => void;
}

export function ChatInterface({
  task,
  sessionToken,
  pid,
  experimentId,
  onComplete,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    DEFAULT_ASSISTANT_MESSAGE,
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isRestoring, setIsRestoring] = useState(true);
  const [isDone, setIsDone] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    setMessages([DEFAULT_ASSISTANT_MESSAGE]);
    setInput("");
    setIsRestoring(true);

    api
      .getChatHistory(sessionToken)
      .then((data) => {
        if (cancelled) return;
        setMessages(
          data.messages.length > 0
            ? data.messages
            : [DEFAULT_ASSISTANT_MESSAGE],
        );
      })
      .catch(() => {
        if (cancelled) return;
        setMessages([DEFAULT_ASSISTANT_MESSAGE]);
      })
      .finally(() => {
        if (!cancelled) {
          setIsRestoring(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [sessionToken, task.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || isRestoring) return;

    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput("");
    setIsLoading(true);

    try {
      const data = await api.sendChatMessage(
        sessionToken,
        pid,
        task.id,
        experimentId,
        updatedMessages,
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.ai_message },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDone = () => {
    setIsDone(true);
    onComplete();
  };

  if (isDone) {
    return (
      <div className="p-6">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <h2 className="text-lg font-semibold text-green-900 mb-2">
            Session Complete
          </h2>
          <p className="text-green-800">Redirecting you back to Prolific...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-2 text-gray-500">
              Thinking...
            </div>
          </div>
        )}
        {isRestoring && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg px-4 py-2 text-gray-500">
              Restoring conversation...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-gray-200 p-4 space-y-2"
      >
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isLoading || isRestoring}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading || isRestoring}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        </div>
        <button
          type="button"
          onClick={handleDone}
          className="w-full bg-green-600 text-white py-2 rounded-lg hover:bg-green-700 transition-colors text-sm"
        >
          I'm done — submit and finish
        </button>
      </form>
    </div>
  );
}
