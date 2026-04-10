export default function SettingsPage() {
  return (
    <div className="flex flex-1 flex-col p-8">
      <h2 className="text-2xl font-bold mb-6">Configuración</h2>
      <div className="space-y-6 max-w-lg">
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Perfil</h3>
          <p className="text-sm text-muted-foreground">
            Gestiona tu información personal y preferencias médicas.
          </p>
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Notificaciones</h3>
          <p className="text-sm text-muted-foreground">
            Configura cómo y cuándo recibir alertas.
          </p>
        </div>
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Privacidad</h3>
          <p className="text-sm text-muted-foreground">
            Controla el acceso a tus datos clínicos.
          </p>
        </div>
      </div>
    </div>
  );
}
