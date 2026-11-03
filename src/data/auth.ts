export type DemoUser = {
  name: string
  role: 'Emergency Officer'
  email: string
}

export const demoUser: DemoUser = {
  name: 'Sumith Choudhary',
  role: 'Emergency Officer',
  email: 'sumith@sahaaya.demo',
}

export function getUserInitials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('')
}

export function getGreeting(date: Date) {
  const hour = date.getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}
