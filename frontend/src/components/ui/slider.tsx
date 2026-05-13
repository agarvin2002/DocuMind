import * as RadixSlider from '@radix-ui/react-slider'
import { cn } from '@/lib/utils'

interface SliderProps {
  value: number
  onValueChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  className?: string
}

export function Slider({ value, onValueChange, min = 1, max = 20, step = 1, className }: SliderProps) {
  return (
    <RadixSlider.Root
      value={[value]}
      onValueChange={([v]) => onValueChange(v)}
      min={min}
      max={max}
      step={step}
      className={cn('relative flex w-full touch-none select-none items-center', className)}
    >
      <RadixSlider.Track className="relative h-1 w-full grow rounded-full bg-bg-border">
        <RadixSlider.Range className="absolute h-full rounded-full bg-accent" />
      </RadixSlider.Track>
      <RadixSlider.Thumb
        className="block h-4 w-4 rounded-full border-2 border-accent bg-bg-elevated shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent cursor-grab active:cursor-grabbing hover:border-accent-hover"
        aria-label="Value"
      />
    </RadixSlider.Root>
  )
}
