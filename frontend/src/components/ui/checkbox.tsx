import * as RadixCheckbox from '@radix-ui/react-checkbox'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CheckboxProps {
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  id?: string
  className?: string
  disabled?: boolean
}

export function Checkbox({ checked, onCheckedChange, id, className, disabled }: CheckboxProps) {
  return (
    <RadixCheckbox.Root
      id={id}
      checked={checked}
      onCheckedChange={(val) => onCheckedChange(val === true)}
      disabled={disabled}
      className={cn(
        'h-4 w-4 shrink-0 rounded border border-bg-border bg-bg-elevated',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent',
        'data-[state=checked]:bg-accent data-[state=checked]:border-accent',
        'disabled:opacity-40 disabled:cursor-not-allowed',
        'transition-colors duration-150',
        className
      )}
    >
      <RadixCheckbox.Indicator className="flex items-center justify-center text-white">
        <Check size={10} strokeWidth={3} />
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  )
}
