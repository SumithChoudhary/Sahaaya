export type FlowShieldVariant = 'dark' | 'light' | 'mono'
export type FlowShieldSize = 'small' | 'medium' | 'large'

type MarkProps = {
  size?: number
  className?: string
  title?: string
}

export function FlowShieldMark({ size = 32, className, title }: MarkProps) {
  return <img
    className={className}
    src="/assets/sahaaya-emblem.webp"
    width={size}
    height={size}
    alt={title ?? ''}
    aria-hidden={title ? undefined : true}
  />
}

type LogoProps = {
  variant?: FlowShieldVariant
  size?: FlowShieldSize
  className?: string
}

export function FlowShieldLogo({ variant = 'dark', size = 'medium', className = '' }: LogoProps) {
  return <span className={`sahaaya-brand-logo logo-${variant} logo-${size} ${className}`.trim()}>
    <img className="sahaaya-brand-image" src="/assets/sahaaya-logo.webp" alt="Sahaaya" />
  </span>
}
