/**
 * Vitest setup file — runs once per worker before any test.
 *
 * - Adds jest-dom matchers (toBeInTheDocument, toHaveTextContent, etc.)
 * - Mocks next/navigation so client components that call useRouter()/
 *   useSearchParams() do not blow up in jsdom (no Next runtime here)
 */
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Node 22+ exposes an experimental localStorage with no setItem unless
// --localstorage-file is passed; jsdom's window.localStorage gets shadowed
// by it. Replace BOTH global and window with a complete in-memory polyfill.
function createMemoryStorage(): Storage {
  let store = new Map<string, string>()
  return {
    get length() {
      return store.size
    },
    clear() {
      store = new Map()
    },
    getItem(key) {
      return store.has(key) ? (store.get(key) as string) : null
    },
    key(index) {
      return Array.from(store.keys())[index] ?? null
    },
    removeItem(key) {
      store.delete(key)
    },
    setItem(key, value) {
      store.set(key, String(value))
    },
  }
}

const memLocal = createMemoryStorage()
const memSession = createMemoryStorage()

Object.defineProperty(globalThis, 'localStorage', {
  value: memLocal,
  configurable: true,
})
Object.defineProperty(globalThis, 'sessionStorage', {
  value: memSession,
  configurable: true,
})
Object.defineProperty(window, 'localStorage', {
  value: memLocal,
  configurable: true,
})
Object.defineProperty(window, 'sessionStorage', {
  value: memSession,
  configurable: true,
})

beforeEach(() => {
  memLocal.clear()
  memSession.clear()
})

afterEach(() => {
  cleanup()
})

// next/navigation hooks need a default mock — tests can override per-suite.
vi.mock('next/navigation', () => {
  return {
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
      refresh: vi.fn(),
      prefetch: vi.fn(),
    }),
    useSearchParams: () => new URLSearchParams(),
    usePathname: () => '/',
    redirect: vi.fn(),
    notFound: vi.fn(),
  }
})
