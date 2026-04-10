export default function ChatPage() {
  return (
    <div className="flex flex-1 flex-col">
      {/* Header */}
      <header className="flex h-14 items-center border-b px-4">
        <h2 className="font-semibold">Nueva consulta</h2>
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4">
        <p className="text-center text-sm text-muted-foreground">
          Describe tus síntomas para comenzar el análisis
        </p>
      </div>

      {/* Input area */}
      <div className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Escribe tus síntomas..."
            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
          />
          <button className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90">
            Enviar
          </button>
        </div>
      </div>
    </div>
  );
}
