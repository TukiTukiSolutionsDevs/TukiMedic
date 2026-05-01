import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, renderHook } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import React from 'react'
import { ThemeProvider } from '../theme-provider'
import { useTheme } from '../use-theme'

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

function ThemeConsumer() {
  const { theme, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <button onClick={() => setTheme('dark')}>set dark</button>
      <button onClick={() => setTheme('light')}>set light</button>
      <button onClick={() => setTheme('system')}>set system</button>
    </div>
  )
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark')
    localStorage.clear()
    mockMatchMedia(false)
  })

  it('mounts without throwing and defaults to system mode', () => {
    expect(() =>
      render(
        <ThemeProvider>
          <ThemeConsumer />
        </ThemeProvider>
      )
    ).not.toThrow()
    expect(screen.getByTestId('current-theme').textContent).toBe('system')
  })

  it('setTheme("dark") adds .dark class to documentElement and persists to localStorage', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )
    await user.click(screen.getByText('set dark'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(localStorage.getItem('tm-theme')).toBe('dark')
  })

  it('setTheme("light") removes .dark class and persists to localStorage', async () => {
    const user = userEvent.setup()
    document.documentElement.classList.add('dark')
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )
    await user.click(screen.getByText('set light'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
    expect(localStorage.getItem('tm-theme')).toBe('light')
  })

  it('setTheme("system") with prefers-color-scheme:dark adds .dark class', async () => {
    mockMatchMedia(true)
    const user = userEvent.setup()
    localStorage.setItem('tm-theme', 'light')
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )
    await user.click(screen.getByText('set system'))
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('setTheme("system") without dark preference does not add .dark class', async () => {
    mockMatchMedia(false)
    const user = userEvent.setup()
    localStorage.setItem('tm-theme', 'dark')
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )
    await user.click(screen.getByText('set system'))
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('restores theme from localStorage on mount', () => {
    localStorage.setItem('tm-theme', 'dark')
    render(
      <ThemeProvider>
        <ThemeConsumer />
      </ThemeProvider>
    )
    expect(screen.getByTestId('current-theme').textContent).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('useTheme() outside ThemeProvider throws a descriptive error', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/)
    spy.mockRestore()
  })
})
