"use client"

import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Plus, X } from 'lucide-react'

interface ChipEditorProps {
  label: string
  items: string[]
  onAdd: (item: string) => void
  onRemove: (index: number) => void
  placeholder?: string
  chipClassName?: string
}

function ChipEditor({ label, items, onAdd, onRemove, placeholder, chipClassName }: ChipEditorProps) {
  const [draft, setDraft] = useState('')

  function handleAdd() {
    const trimmed = draft.trim()
    if (!trimmed) return
    onAdd(trimmed)
    setDraft('')
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleAdd()
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2 min-h-[28px]">
        {items.map((item, i) => (
          <span
            key={i}
            data-testid="chip"
            className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-medium ${chipClassName ?? 'border-border bg-muted text-foreground'}`}
          >
            {item}
            <button
              type="button"
              onClick={() => onRemove(i)}
              aria-label={`Quitar ${item}`}
              className="inline-flex items-center opacity-60 hover:opacity-100 transition-opacity"
            >
              <X size={12} aria-hidden="true" />
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder ?? `Agregar ${label.toLowerCase()}`}
          aria-label={`Nueva entrada de ${label}`}
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleAdd}
          disabled={!draft.trim()}
          aria-label={`Agregar ${label}`}
        >
          <Plus size={14} aria-hidden="true" />
          Agregar
        </Button>
      </div>
    </div>
  )
}

export function HealthTab() {
  const [allergies, setAllergies] = useState<string[]>([])
  const [medications, setMedications] = useState<string[]>([])
  const [conditions, setConditions] = useState<string[]>([])

  function handleSave() {
    // TODO: PATCH /api/v1/auth/me/health when endpoint is ready
  }

  return (
    <div className="max-w-xl flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Alergias conocidas</CardTitle>
        </CardHeader>
        <CardContent>
          <ChipEditor
            label="Alergias"
            items={allergies}
            onAdd={(item) => setAllergies((prev) => [...prev, item])}
            onRemove={(i) => setAllergies((prev) => prev.filter((_, idx) => idx !== i))}
            placeholder="Ej: Penicilina, Polen"
            chipClassName="border-amber-300/60 bg-amber-50 text-amber-900 dark:border-amber-700/50 dark:bg-amber-950/40 dark:text-amber-100"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Medicación activa</CardTitle>
        </CardHeader>
        <CardContent>
          <ChipEditor
            label="Medicación"
            items={medications}
            onAdd={(item) => setMedications((prev) => [...prev, item])}
            onRemove={(i) => setMedications((prev) => prev.filter((_, idx) => idx !== i))}
            placeholder="Ej: Levotiroxina 75mcg"
            chipClassName="border-blue-300/60 bg-blue-50 text-blue-900 dark:border-blue-700/50 dark:bg-blue-950/40 dark:text-blue-100"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Condiciones crónicas</CardTitle>
        </CardHeader>
        <CardContent>
          <ChipEditor
            label="Condiciones"
            items={conditions}
            onAdd={(item) => setConditions((prev) => [...prev, item])}
            onRemove={(i) => setConditions((prev) => prev.filter((_, idx) => idx !== i))}
            placeholder="Ej: Hipotiroidismo"
            chipClassName="border-green-300/60 bg-green-50 text-green-900 dark:border-green-700/50 dark:bg-green-950/40 dark:text-green-100"
          />
        </CardContent>
      </Card>

      <Button onClick={handleSave} className="self-start">
        Guardar ficha
      </Button>
    </div>
  )
}
