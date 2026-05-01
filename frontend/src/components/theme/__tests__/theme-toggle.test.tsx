import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { ThemeProvider } from '../theme-provider'
import { ThemeToggle } from '../theme-toggle'

function mockMatchMedia(matches: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

function renderToggle() {
  return render(
    <ThemeProvider defaultTheme="light">
      <ThemeToggle />
    </ThemeProvider>
  )
}

describe('ThemeToggle', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark')
    localStorage.clear()
    mockMatchMedia(false)
  })

  it('renders a button with an accessible label', () => {
    renderToggle()
    const btn = screen.getByRole('button')
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-label')
  })

  it('shows Sun icon when theme is light', () => {
    renderToggle()
    expect(screen.getByTestId('icon-sun')).toBeInTheDocument()
  })

  it('cycles light → dark on first click', async () => {
    const user = userEvent.setup()
    renderToggle()
    await user.click(screen.getByRole('button'))
    expect(screen.getByTestId('icon-moon')).toBeInTheDocument()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('cycles dark → system on second click', async () => {
    const user = userEvent.setup()
    renderToggle()
    await user.click(screen.getByRole('button'))
    await user.click(screen.getByRole('button'))
    expect(screen.getByTestId('icon-monitor')).toBeInTheDocument()
  })

  it('cycles system → light on third click', async () => {
    const user = userEvent.setup()
    renderToggle()
    await user.click(screen.getByRole('button'))
    await user.click(screen.getByRole('button'))
    await user.click(screen.getByRole('button'))
    expect(screen.getByTestId('icon-sun')).toBeInTheDocument()
  })
})
