import { cn } from '@/lib/utils'

interface StreamingTextProps {
  text: string
  isStreaming?: boolean
  className?: string
}

function renderWithCitations(text: string): (string | JSX.Element)[] {
  const parts = text.split(/(\[\d+\])/g)
  return parts.map((part, i) => {
    const match = part.match(/^\[(\d+)\]$/)
    if (match) {
      return (
        <sup
          key={i}
          className="mx-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-accent/15 px-1 text-[10px] font-bold text-accent font-mono not-italic"
        >
          {match[1]}
        </sup>
      )
    }
    return part
  })
}

export function StreamingText({ text, isStreaming, className }: StreamingTextProps) {
  return (
    <p
      className={cn(
        'text-sm text-txt-primary leading-7 whitespace-pre-wrap',
        isStreaming && 'streaming-cursor',
        className
      )}
    >
      {renderWithCitations(text)}
    </p>
  )
}
