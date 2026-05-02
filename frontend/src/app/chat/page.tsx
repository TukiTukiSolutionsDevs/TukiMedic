"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useChatWS } from "@/hooks/use-chat-ws";
import { useDocumentUpload } from "@/hooks/use-document-upload";
import { useChatStore, type ConnectionStatus } from "@/store/chat-store";
import { useAuthStore } from "@/store/auth-store";
import { Conversation } from "@/components/chat/conversation";
import { AgentsPanel } from "@/components/chat/agents-panel";
import { TriageStatus } from "@/components/chat/triage-status";
import { ChatInput } from "@/components/chat/chat-input";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATUS_CONFIG: Record<ConnectionStatus, { dot: string; label: string }> =
  {
    disconnected: { dot: "bg-gray-400", label: "Desconectado" },
    connecting: { dot: "bg-amber-400 animate-pulse", label: "Conectando..." },
    authenticating: {
      dot: "bg-amber-400 animate-pulse",
      label: "Autenticando...",
    },
    connected: { dot: "bg-green-500", label: "Conectado" },
    error: { dot: "bg-red-500", label: "Error de conexión" },
  };

function ConnectionBadge({ status }: { status: ConnectionStatus }) {
  const { dot, label } = STATUS_CONFIG[status];
  return (
    <div
      className="flex items-center gap-1.5 text-xs text-muted-foreground"
      data-testid="connection-badge"
    >
      <span className={`h-2 w-2 rounded-full ${dot}`} />
      {label}
    </div>
  );
}

export default function ChatPage() {
  const router = useRouter();
  const {
    sendMessage,
    connectionStatus,
    triageLevel,
    escalationPayload,
  } = useChatWS();
  const {
    uploadDocument,
    isUploading,
    uploadError,
    lastUploadedDoc,
  } = useDocumentUpload();
  const accessToken = useAuthStore((s) => s.accessToken);
  const subscriptionTier = useAuthStore(
    (s) => s.user?.subscriptionTier ?? "free",
  );
  const {
    messages,
    streamingMessage,
    isLoading,
    currentAgentNode,
    currentCaseId,
  } = useChatStore();

  const [exportingPdf, setExportingPdf] = useState(false);

  // Escalation: when the WS reports a red triage with red flags, persist the
  // payload to sessionStorage and redirect to /escalation. We do NOT block
  // the chat — the user is shown the urgent screen but can come back.
  useEffect(() => {
    if (triageLevel === "red" && escalationPayload) {
      try {
        sessionStorage.setItem(
          "tm-escalation",
          JSON.stringify({
            ...escalationPayload,
            caseId: escalationPayload.caseId ?? currentCaseId ?? null,
            at: new Date().toISOString(),
          }),
        );
      } catch {
        // sessionStorage may be unavailable in some browsers/private mode.
      }
      router.push("/escalation");
    }
  }, [triageLevel, escalationPayload, currentCaseId, router]);

  const handleExportPdf = useCallback(async () => {
    if (!currentCaseId || !accessToken) return;
    setExportingPdf(true);
    try {
      const r = await fetch(
        `${API}/api/v1/cases/${currentCaseId}/export/pdf`,
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        },
      );
      if (!r.ok) throw new Error("Error al generar PDF");
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `case_${currentCaseId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    } finally {
      setExportingPdf(false);
    }
  }, [currentCaseId, accessToken]);

  const handleSend = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || connectionStatus !== "connected" || isLoading) return;
      sendMessage(trimmed, currentCaseId);
    },
    [sendMessage, connectionStatus, isLoading, currentCaseId],
  );

  const handleFileSelect = useCallback(
    (file: File) => {
      uploadDocument(file, currentCaseId ?? undefined);
    },
    [uploadDocument, currentCaseId],
  );

  const handlePromptFromExample = useCallback(
    (text: string) => handleSend(text),
    [handleSend],
  );

  const isInputDisabled = connectionStatus !== "connected" || isLoading;
  const isPaidTier = subscriptionTier === "paid";

  return (
    <div
      data-testid="chat-page"
      className="flex flex-1 flex-col bg-[var(--tm-bg)]"
    >
      <header className="flex h-14 items-center justify-between border-b px-4">
        <div className="flex items-center gap-3">
          <h2 className="font-semibold">Nueva consulta</h2>
          <TriageStatus level={triageLevel} isActive={isLoading} />
        </div>
        <div className="flex items-center gap-3">
          {currentCaseId && (
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={exportingPdf}
              data-testid="export-pdf"
              className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-50"
            >
              {exportingPdf ? "Generando..." : "Exportar PDF"}
            </button>
          )}
          <ConnectionBadge status={connectionStatus} />
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <div className="flex flex-1 min-w-0 flex-col">
          <Conversation
            messages={messages}
            streamingMessage={streamingMessage}
            isLoading={isLoading}
            currentAgentNode={currentAgentNode}
            onPrompt={handlePromptFromExample}
            onDownloadPdf={currentCaseId ? handleExportPdf : undefined}
          />

          <div className="border-t p-3">
            {uploadError && (
              <p
                data-testid="upload-error"
                className="mb-2 text-xs text-[var(--tm-red-600)]"
              >
                {uploadError}
              </p>
            )}
            {lastUploadedDoc && !isUploading && !uploadError && (
              <p
                data-testid="upload-success"
                className="mb-2 text-xs text-[var(--tm-green-700)]"
              >
                Archivo subido — procesando en segundo plano
              </p>
            )}
            <ChatInput
              onSend={handleSend}
              onFileSelect={handleFileSelect}
              disabled={isInputDisabled}
              isPaidTier={isPaidTier}
              isUploading={isUploading}
            />
          </div>
        </div>

        <AgentsPanel
          currentAgent={currentAgentNode}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
