import { useId } from 'react'

export type FlowShieldVariant = 'dark' | 'light' | 'mono'
export type FlowShieldSize = 'small' | 'medium' | 'large'

type MarkProps = {
  size?: number
  className?: string
  title?: string
}

export function FlowShieldMark({ size = 32, className, title }: MarkProps) {
  const gradientId = `flowshield-${useId().replaceAll(':', '')}`
  return <svg className={className} width={size} height={size} viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role={title ? 'img' : undefined} aria-hidden={title ? undefined : true} aria-label={title}>
    <defs>
      <linearGradient id={gradientId} x1="11" y1="53" x2="51" y2="11" gradientUnits="userSpaceOnUse">
        <stop stopColor="#0EA5E9" />
        <stop offset="0.52" stopColor="#22D3EE" />
        <stop offset="1" stopColor="#A3E635" />
      </linearGradient>
    </defs>
    <path d="M48.5 14.5C43.8 10.2 36.9 8.4 29.6 9.3C21.1 10.3 15.2 15 14.6 21.7C13.8 30.1 22.1 32.2 32.8 35.1C43 37.8 50.7 40 49.4 48.1C48.4 54.7 41.3 59.2 32.2 59.2C24.4 59.2 17.4 56.3 12.7 51.3" stroke={`url(#${gradientId})`} strokeWidth="8.5" strokeLinecap="round" />
    <path d="M48.8 14.7C53.2 19.3 55.5 25.1 55.5 31.4" stroke="#22D3EE" strokeOpacity=".45" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
}

type LogoProps = {
  variant?: FlowShieldVariant
  size?: FlowShieldSize
  className?: string
}

export function FlowShieldLogo({ variant = 'dark', size = 'medium', className = '' }: LogoProps) {
  const markSize = size === 'small' ? 28 : size === 'large' ? 42 : 36
  return <span className={`sahaaya-brand-logo logo-${variant} logo-${size} ${className}`.trim()}>
    <FlowShieldMark size={markSize} className="flowshield-mark" />
    <span className="sahaaya-wordmark">SAHAAYA</span>
  </span>
}
