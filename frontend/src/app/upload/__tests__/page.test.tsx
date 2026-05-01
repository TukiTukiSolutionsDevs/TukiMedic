import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import React from 'react'

import UploadPage from '../page'
import { useDocumentUpload } from '@/hooks/use-document-upload'

vi.mock('@/hooks/use-document-upload')

const defaultReturn = {
  uploadDocument: vi.fn(),
  isUploading: false,
  uploadError: null,
  lastUploadedDoc: null,
}

describe('UploadPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useDocumentUpload).mockReturnValue(defaultReturn)
  })

  it('renders heading and upload button', () => {
    render(<UploadPage />)
    expect(screen.getByRole('heading', { name: /subir documento/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /seleccionar archivo/i })).toBeInTheDocument()
  })

  it('disables button while uploading', () => {
    vi.mocked(useDocumentUpload).mockReturnValue({ ...defaultReturn, isUploading: true })
    render(<UploadPage />)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('shows error alert when uploadError is set', () => {
    vi.mocked(useDocumentUpload).mockReturnValue({
      ...defaultReturn,
      uploadError: 'Error al subir archivo',
    })
    render(<UploadPage />)
    expect(screen.getByRole('alert')).toHaveTextContent('Error al subir archivo')
  })
})
