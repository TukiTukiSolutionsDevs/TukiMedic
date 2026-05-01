'use client'

import { useRef, type ChangeEvent } from 'react'
import { Loader2 } from 'lucide-react'

import { useDocumentUpload } from '@/hooks/use-document-upload'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export default function UploadPage() {
  const { uploadDocument, isUploading, uploadError, lastUploadedDoc } = useDocumentUpload()
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    await uploadDocument(file)
    // Reset so the same file can be re-submitted after an error
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <div className="container mx-auto max-w-lg space-y-6 py-8">
      <h1 className="text-2xl font-bold">Subir documento</h1>

      <Card>
        <CardHeader>
          <CardTitle>Seleccioná un archivo</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <input
            ref={inputRef}
            id="file-input"
            type="file"
            accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
            className="sr-only"
            onChange={handleFileChange}
            disabled={isUploading}
            aria-label="Seleccionar archivo"
          />

          <Button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 size-4 animate-spin" />
                Subiendo…
              </>
            ) : (
              'Seleccionar archivo'
            )}
          </Button>

          {uploadError && (
            <div
              role="alert"
              aria-live="polite"
              className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
            >
              {uploadError}
            </div>
          )}

          {lastUploadedDoc && (
            <div
              role="status"
              className="rounded-md border border-green-500/40 bg-green-50/50 px-3 py-2 text-sm"
            >
              Documento subido exitosamente (ID: {lastUploadedDoc.document_id})
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
