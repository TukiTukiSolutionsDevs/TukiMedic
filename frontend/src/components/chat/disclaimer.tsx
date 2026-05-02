'use client'

export const BASE_DISCLAIMER =
  'TukiMedic no reemplaza la consulta m\u00e9dica presencial. Esta orientaci\u00f3n es informativa y no constituye diagn\u00f3stico, tratamiento ni prescripci\u00f3n m\u00e9dica. En caso de emergencia, llam\u00e1 al 106\u00a0/\u00a0SAMU o dirigite a la guardia m\u00e1s cercana.'

interface DisclaimerProps {
  compact?: boolean
}

export function Disclaimer({ compact = false }: DisclaimerProps) {
  return (
    <p
      data-testid="disclaimer"
      className={`leading-relaxed text-muted-foreground ${compact ? 'text-[11px]' : 'text-xs'}`}
    >
      {BASE_DISCLAIMER}
    </p>
  )
}
