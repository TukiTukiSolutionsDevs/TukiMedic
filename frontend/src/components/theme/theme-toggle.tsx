"use client"

import React from 'react'
import { Sun, Moon, Monitor } from 'lucide-react'
import { useTheme, type Theme } from './use-theme'

const CYCLE: Theme[] = ['light', 'dark', 'system']

const NEXT_LABEL: Record<Theme, string> = {
  light: 'Switch to dark mode',
  dark: 'Switch to system mode',
  system: 'Switch to light mode',
}

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  function handleClick() {
    const idx = CYCLE.indexOf(theme)
    const next = CYCLE[(idx + 1) % CYCLE.length]
    setTheme(next)
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      aria-label={NEXT_LABEL[theme]}
    >
      {theme === 'light' && <Sun data-testid="icon-sun" />}
      {theme === 'dark' && <Moon data-testid="icon-moon" />}
      {theme === 'system' && <Monitor data-testid="icon-monitor" />}
    </button>
  )
}
