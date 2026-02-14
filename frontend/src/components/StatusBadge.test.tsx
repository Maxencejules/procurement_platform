import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from './StatusBadge'

describe('StatusBadge', () => {
  it('renders the correct label for draft status', () => {
    render(<StatusBadge status="draft" />)
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })

  it('renders the correct label for approved status', () => {
    render(<StatusBadge status="approved" />)
    expect(screen.getByText('Approved')).toBeInTheDocument()
  })

  it('renders the correct label for pending_approval status', () => {
    render(<StatusBadge status="pending_approval" />)
    expect(screen.getByText('Pending Approval')).toBeInTheDocument()
  })

  it('applies the correct CSS class', () => {
    const { container } = render(<StatusBadge status="rejected" />)
    expect(container.querySelector('.badge-rejected')).toBeInTheDocument()
  })

  it('renders unknown status as-is', () => {
    render(<StatusBadge status="unknown_status" />)
    expect(screen.getByText('unknown_status')).toBeInTheDocument()
  })
})
