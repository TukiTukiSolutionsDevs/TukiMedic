import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ChatPage from "@/app/chat/page";
import { useAuthStore } from "@/store/auth-store";
import { useChatStore } from "@/store/chat-store";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn() }),
}));

interface WSMockState {
  triageLevel: "green" | "yellow" | "red" | null;
  escalationPayload: { caseId?: string; redFlags: string[] } | null;
  connectionStatus: "connected" | "disconnected" | "connecting";
}

const wsMockState: WSMockState = {
  triageLevel: null,
  escalationPayload: null,
  connectionStatus: "connected",
};

vi.mock("@/hooks/use-chat-ws", () => ({
  useChatWS: () => ({
    sendMessage: vi.fn(),
    connectionStatus: wsMockState.connectionStatus,
    isConnected: wsMockState.connectionStatus === "connected",
    disconnect: vi.fn(),
    activeAgents: [],
    triageLevel: wsMockState.triageLevel,
    escalationPayload: wsMockState.escalationPayload,
  }),
}));

vi.mock("@/hooks/use-document-upload", () => ({
  useDocumentUpload: () => ({
    uploadDocument: vi.fn(),
    isUploading: false,
    uploadError: null,
    lastUploadedDoc: null,
  }),
}));

function seedAuth(tier: string = "free") {
  useAuthStore.setState({
    user: {
      id: "u1",
      email: "p@tuki.dev",
      displayName: "Paciente",
      role: "customer",
      subscriptionTier: tier,
    },
    accessToken: "tok",
    refreshToken: "ref",
    isAuthenticated: true,
  });
}

beforeEach(() => {
  pushMock.mockReset();
  wsMockState.triageLevel = null;
  wsMockState.escalationPayload = null;
  wsMockState.connectionStatus = "connected";
  useChatStore.setState({
    messages: [],
    streamingMessage: null,
    isLoading: false,
    currentAgentNode: null,
    currentCaseId: null,
  });
  seedAuth();
  // sessionStorage cleanup
  if (typeof window !== "undefined") {
    window.sessionStorage.clear();
  }
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChatPage layout", () => {
  it("renders the chat page shell", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("chat-page")).toBeInTheDocument();
  });

  it("shows the connection badge", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("connection-badge")).toBeInTheDocument();
  });

  it("does not show the triage status when level is null", () => {
    render(<ChatPage />);
    expect(screen.queryByTestId("triage-status")).not.toBeInTheDocument();
  });

  it("shows the triage status with correct level when set", () => {
    wsMockState.triageLevel = "yellow";
    render(<ChatPage />);
    const ts = screen.getByTestId("triage-status");
    expect(ts).toBeInTheDocument();
    expect(ts).toHaveAttribute("data-level", "yellow");
  });

  it("hides the export-pdf button when no current case", () => {
    render(<ChatPage />);
    expect(screen.queryByTestId("export-pdf")).not.toBeInTheDocument();
  });

  it("shows the export-pdf button when a case is loaded", () => {
    useChatStore.setState({ currentCaseId: "case-1" });
    render(<ChatPage />);
    expect(screen.getByTestId("export-pdf")).toBeInTheDocument();
  });
});

describe("ChatPage escalation redirect", () => {
  it("redirects to /escalation when triage=red with payload", () => {
    wsMockState.triageLevel = "red";
    wsMockState.escalationPayload = { redFlags: ["dolor toráxico"] };
    render(<ChatPage />);
    expect(pushMock).toHaveBeenCalledWith("/escalation");
  });

  it("persists the escalation payload to sessionStorage", () => {
    wsMockState.triageLevel = "red";
    wsMockState.escalationPayload = { redFlags: ["disnea"] };
    render(<ChatPage />);
    const stored = window.sessionStorage.getItem("tm-escalation");
    expect(stored).not.toBeNull();
    const parsed = JSON.parse(stored!);
    expect(parsed.redFlags).toEqual(["disnea"]);
    expect(typeof parsed.at).toBe("string");
  });

  it("does NOT redirect when triage=red but no payload yet", () => {
    wsMockState.triageLevel = "red";
    wsMockState.escalationPayload = null;
    render(<ChatPage />);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("does NOT redirect on green triage", () => {
    wsMockState.triageLevel = "green";
    wsMockState.escalationPayload = { redFlags: [] };
    render(<ChatPage />);
    expect(pushMock).not.toHaveBeenCalled();
  });

  it("does NOT redirect on yellow triage", () => {
    wsMockState.triageLevel = "yellow";
    wsMockState.escalationPayload = { redFlags: ["fiebre"] };
    render(<ChatPage />);
    expect(pushMock).not.toHaveBeenCalled();
  });
});

describe("ChatPage agents panel and conversation", () => {
  it("hides the agents panel when not loading and no agent", () => {
    render(<ChatPage />);
    expect(screen.queryByTestId("agents-panel")).not.toBeInTheDocument();
  });

  it("shows the agents panel while a node is processing", () => {
    useChatStore.setState({
      isLoading: true,
      currentAgentNode: "triage",
    });
    render(<ChatPage />);
    expect(screen.getByTestId("agents-panel")).toBeInTheDocument();
  });
});
