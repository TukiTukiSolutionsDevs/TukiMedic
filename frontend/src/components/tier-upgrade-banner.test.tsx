/**
 * Tests for the <TierUpgradeBanner /> presentational component.
 *
 * Used wherever the frontend catches a tier_required 403 from the backend
 * (paid features: chat with specialists, document upload, PDF export,
 * history > 7 days). The banner replaces what would otherwise be a
 * generic error screen.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { TierUpgradeBanner } from './tier-upgrade-banner'

describe('TierUpgradeBanner', () => {
  it('renders the required tier and current tier in human copy', () => {
    render(<TierUpgradeBanner requiredTier="paid" currentTier="free" />)

    // The exact wording can evolve; we assert that BOTH tiers are surfaced
    // so the user understands the gap, not just that "something is locked".
    const root = screen.getByRole('alert')
    expect(root).toHaveTextContent(/paid/i)
    expect(root).toHaveTextContent(/free/i)
  })

  it('exposes itself as an alert for assistive tech', () => {
    render(<TierUpgradeBanner requiredTier="paid" currentTier="free" />)
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('calls onUpgrade when the upgrade CTA is clicked', async () => {
    const onUpgrade = vi.fn()
    render(
      <TierUpgradeBanner
        requiredTier="paid"
        currentTier="free"
        onUpgrade={onUpgrade}
      />,
    )

    await userEvent.setup().click(screen.getByRole('button', { name: /mejorar/i }))
    expect(onUpgrade).toHaveBeenCalledTimes(1)
  })

  it('calls onDismiss when the close CTA is clicked', async () => {
    const onDismiss = vi.fn()
    render(
      <TierUpgradeBanner
        requiredTier="paid"
        currentTier="free"
        onDismiss={onDismiss}
      />,
    )

    await userEvent
      .setup()
      .click(screen.getByRole('button', { name: /cerrar/i }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
  })

  it('hides the upgrade button when no onUpgrade handler is provided', () => {
    render(<TierUpgradeBanner requiredTier="paid" currentTier="free" />)
    expect(
      screen.queryByRole('button', { name: /mejorar/i }),
    ).not.toBeInTheDocument()
  })

  it('hides the close button when no onDismiss handler is provided', () => {
    render(<TierUpgradeBanner requiredTier="paid" currentTier="free" />)
    expect(
      screen.queryByRole('button', { name: /cerrar/i }),
    ).not.toBeInTheDocument()
  })
})
