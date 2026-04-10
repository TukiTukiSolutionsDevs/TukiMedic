'use client'

import { useState } from 'react'
import { useAuthStore } from '@/store/auth-store'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export interface UploadedDoc {
  document_id: string
  status: string
  processing_status: string
}

export interface UseDocumentUploadReturn {
  uploadDocument: (file: File, caseId?: string) => Promise<UploadedDoc | null>
  isUploading: boolean
  uploadError: string | null
  lastUploadedDoc: UploadedDoc | null
}

export function useDocumentUpload(): UseDocumentUploadReturn {
  const accessToken = useAuthStore((s) => s.accessToken)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [lastUploadedDoc, setLastUploadedDoc] = useState<UploadedDoc | null>(null)

  async function uploadDocument(file: File, caseId?: string): Promise<UploadedDoc | null> {
    if (!accessToken) {
      setUploadError('No autenticado')
      return null
    }

    setIsUploading(true)
    setUploadError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      if (caseId) formData.append('case_id', caseId)

      const response = await fetch(`${API_BASE}/api/v1/documents/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        body: formData,
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: 'Error desconocido' }))
        throw new Error(err.detail ?? `Error ${response.status}`)
      }

      const doc = (await response.json()) as UploadedDoc
      setLastUploadedDoc(doc)
      return doc
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al subir archivo'
      setUploadError(message)
      return null
    } finally {
      setIsUploading(false)
    }
  }

  return { uploadDocument, isUploading, uploadError, lastUploadedDoc }
}
