import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import React from 'react'

import { CaseRow, type HistoryCase } from '@/components/history/case-row'
import { FilterBar } from '@/components/history/filter-bar'
import { EmptyState } from '@/components/history/empty-state'

const BASE_CASE: HistoryCase = {
  id: 'c1',
  title: 'Dolor de cabeza',
  chief_complaint: 'Me duele la cabeza',
  triage_level: 'yellow',
  specialties: ['Neurología'],
  status: 'activo',
  created_at: '2026-04-01T00:00:00Z',
}

// ---------------------------------------------------------------------------
// CaseRow
// ---------------------------------------------------------------------------

describe('CaseRow', () => {
  it('renders the case title', () => {
    render(<CaseRow c={BASE_CASE} isPaid={false} />)
    expect(screen.getByText('Dolor de cabeza')).toBeInTheDocument()
  })

  it('renders the triage dot', () => {
    render(<CaseRow c={BASE_CASE} isPaid={false} />)
    expect(screen.getByTestId('triage-dot')).toBeInTheDocument()
  })

  it('"Ver" link points to /cases/[id]', () => {
    render(<CaseRow c={BASE_CASE} isPaid={false} />)
    expect(screen.getByRole('link', { name: /ver/i })).toHaveAttribute('href', '/cases/c1')
  })

  it('shows PDF export button for paid user', () => {
    render(<CaseRow c={BASE_CASE} isPaid={true} />)
    expect(screen.getByTestId('pdf-button')).toBeInTheDocument()
  })

  it('shows lock icon for free user', () => {
    render(<CaseRow c={BASE_CASE} isPaid={false} />)
    expect(screen.getByTestId('pdf-locked')).toBeInTheDocument()
  })

  it('renders overflow chip when specialties exceed 3', () => {
    const c: HistoryCase = {
      ...BASE_CASE,
      specialties: ['Neurología', 'Cardiología', 'Pediatría', 'Dermatología'],
    }
    render(<CaseRow c={c} isPaid={false} />)
    expect(screen.getByText('+1')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// FilterBar
// ---------------------------------------------------------------------------

const NOOP = vi.fn()

describe('FilterBar', () => {
  function renderFilterBar(overrides: Partial<Parameters<typeof FilterBar>[0]> = {}) {
    return render(
      <FilterBar
        query=""
        onQueryChange={NOOP}
        triage="all"
        onTriageChange={NOOP}
        since="all"
        onSinceChange={NOOP}
        {...overrides}
      />,
    )
  }

  it('renders the search input', () => {
    renderFilterBar()
    expect(screen.getByPlaceholderText(/buscar por motivo/i)).toBeInTheDocument()
  })

  it('renders all 4 triage chips', () => {
    renderFilterBar()
    const group = screen.getByRole('group', { name: /filtrar por triage/i })
    expect(within(group).getByRole('button', { name: /todos/i })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: /verde/i })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: /amarillo/i })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: /rojo/i })).toBeInTheDocument()
  })

  it('calls onQueryChange when typing in the search input', () => {
    const onQueryChange = vi.fn()
    renderFilterBar({ onQueryChange })
    fireEvent.change(screen.getByPlaceholderText(/buscar por motivo/i), {
      target: { value: 'fiebre' },
    })
    expect(onQueryChange).toHaveBeenCalledWith('fiebre')
  })

  it('calls onTriageChange when clicking a triage chip', () => {
    const onTriageChange = vi.fn()
    renderFilterBar({ onTriageChange })
    fireEvent.click(screen.getByRole('button', { name: /verde/i }))
    expect(onTriageChange).toHaveBeenCalledWith('green')
  })
})

// ---------------------------------------------------------------------------
// EmptyState
// ---------------------------------------------------------------------------

describe('EmptyState', () => {
  it('shows "Aún no tenés consultas" when no filters are active', () => {
    render(<EmptyState hasFilters={false} onClearFilters={vi.fn()} />)
    expect(screen.getByText(/aún no tenés consultas/i)).toBeInTheDocument()
  })

  it('shows "Iniciar consulta" CTA when no filters are active', () => {
    render(<EmptyState hasFilters={false} onClearFilters={vi.fn()} />)
    expect(screen.getByRole('link', { name: /iniciar consulta/i })).toBeInTheDocument()
  })

  it('shows "Limpiar filtros" button when filters are active', () => {
    render(<EmptyState hasFilters={true} onClearFilters={vi.fn()} />)
    expect(screen.getByRole('button', { name: /limpiar filtros/i })).toBeInTheDocument()
  })

  it('"Limpiar filtros" calls onClearFilters', () => {
    const onClearFilters = vi.fn()
    render(<EmptyState hasFilters={true} onClearFilters={onClearFilters} />)
    fireEvent.click(screen.getByRole('button', { name: /limpiar filtros/i }))
    expect(onClearFilters).toHaveBeenCalledTimes(1)
  })
})
