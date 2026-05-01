import { useContext } from 'react'
import { ThemeContext } from './theme-provider'
export type { Theme } from './theme-provider'

export function useTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be called within a ThemeProvider')
  }
  return ctx
}
