import { JSX, useState } from 'react'
import { Spinner } from './Spinner.tsx'

export type ButtonProps = {
  action?: () => Promise<void>
  loading?: boolean
  size?: 'small' | 'medium' | 'large'
  transparent?: boolean
} & JSX.IntrinsicElements['button']
export function Button({
  action,
  loading = false,
  size = 'medium',
  transparent = false,

  // button
  children,
  onClick,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  const actionable =
    props.type === 'submit' || onClick != null || action != null

  const [isPending, setIsPending] = useState(false)

  const showProgress = loading || isPending
  const sizeClass =
    size === 'small'
      ? 'px-1 py-0'
      : size === 'large'
      ? 'px-3 py-2'
      : 'px-2 py-1'

  return (
    <button
      {...props}
      onClick={async (event) => {
        onClick?.(event)
        if (action != null && !event.defaultPrevented) {
          event.preventDefault()
          try {
            setIsPending(true)
            await action()
          } finally {
            setIsPending(false)
          }
        }
      }}
      tabIndex={props?.tabIndex ?? (actionable ? 0 : -1)}
      disabled={disabled || showProgress}
      className={[
        'relative overflow-hidden',
        'inline-block rounded-md',
        'focus:outline-none focus:ring-2 focus:ring-offset-2',
        'transition duration-300 ease-in-out',
        transparent
          ? 'bg-transparent text-purple-600 hover:bg-purple-100 focus:ring-purple-500'
          : 'bg-purple-600 text-white hover:bg-purple-700 focus:ring-purple-800',
        sizeClass,
        className,
      ].join(' ')}
    >
      {showProgress && (
        <span className="absolute inset-0 z-10 flex items-center justify-center">
          <Spinner size={size} />
        </span>
      )}

      <span className={showProgress ? 'invisible' : 'visible'}>{children}</span>
    </button>
  )
}
