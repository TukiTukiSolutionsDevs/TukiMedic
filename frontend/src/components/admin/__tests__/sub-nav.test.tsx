import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { AdminSubNav } from '@/components/admin/sub-nav'

let mockPathname = '/admin/audit'

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
}))

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string
    children: React.ReactNode
    [key: string]: unknown
  }) => (
    <a href={href} {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}>
      {children}
    </a>
  ),
}))

afterEach(() => {
  mockPathname = '/admin/audit'
})

describe('AdminSubNav', () => {
  it('renders all 4 nav links', () => {
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-audit')).toBeInTheDocument()
    expect(screen.getByTestId('admin-nav-credentials')).toBeInTheDocument()
    expect(screen.getByTestId('admin-nav-users')).toBeInTheDocument()
    expect(screen.getByTestId('admin-nav-kb')).toBeInTheDocument()
  })

  it('marks audit as active on /admin/audit', () => {
    mockPathname = '/admin/audit'
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-audit')).toHaveAttribute('data-active', 'true')
    expect(screen.getByTestId('admin-nav-users')).toHaveAttribute('data-active', 'false')
  })

  it('marks credentials as active on /admin/credentials', () => {
    mockPathname = '/admin/credentials'
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-credentials')).toHaveAttribute('data-active', 'true')
    expect(screen.getByTestId('admin-nav-audit')).toHaveAttribute('data-active', 'false')
  })

  it('marks users as active on /admin/users', () => {
    mockPathname = '/admin/users'
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-users')).toHaveAttribute('data-active', 'true')
    expect(screen.getByTestId('admin-nav-kb')).toHaveAttribute('data-active', 'false')
  })

  it('marks kb as active on /admin/kb', () => {
    mockPathname = '/admin/kb'
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-kb')).toHaveAttribute('data-active', 'true')
    expect(screen.getByTestId('admin-nav-credentials')).toHaveAttribute('data-active', 'false')
  })

  it('links have correct hrefs', () => {
    render(<AdminSubNav />)
    expect(screen.getByTestId('admin-nav-audit')).toHaveAttribute('href', '/admin/audit')
    expect(screen.getByTestId('admin-nav-credentials')).toHaveAttribute('href', '/admin/credentials')
    expect(screen.getByTestId('admin-nav-users')).toHaveAttribute('href', '/admin/users')
    expect(screen.getByTestId('admin-nav-kb')).toHaveAttribute('href', '/admin/kb')
  })
})
