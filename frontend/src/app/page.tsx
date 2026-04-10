export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8">
      <h2 className="text-2xl font-bold">Bienvenido a MedAgent</h2>
      <p className="text-muted-foreground text-center max-w-md">
        Sistema de análisis clínico coordinado. Describe tus síntomas y nuestro
        equipo de especialistas virtuales analizará tu caso.
      </p>
      <button className="rounded-md bg-primary px-4 py-2 text-primary-foreground hover:bg-primary/90">
        Nueva consulta
      </button>
    </div>
  );
}
