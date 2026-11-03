export type Priority = 'Critical' | 'High' | 'Medium' | 'Low'
export type Area = {
  id: string
  name: string
  lat: number
  lng: number
  population: number
  severity: number
  injured: number
  trapped: number
  requests: number
  priority: Priority
  score: number
}

export type ResourceId = 'ambulances' | 'rescue-teams' | 'medical-kits' | 'food-kits' | 'water-units' | 'shelter-capacity' | 'emergency-transport'
export type RequestStatus = 'Pending' | 'Processing' | 'Assigned' | 'Completed'
export type RequestType = 'Medical' | 'Rescue' | 'Food' | 'Water' | 'Shelter' | 'Evacuation'

export const demoIncident = {
  title: 'Monsoon response',
  label: 'MONSOON RESPONSE · DEMO ENVIRONMENT',
  state: 'DEMO SCENARIO',
  disclaimer: 'Fictional demonstration data · Not live emergency information',
}

export const priorityLevels: { name: Priority; color: string; radiusMeters: number }[] = [
  { name: 'Critical', color: '#fb5d5d', radiusMeters: 630 },
  { name: 'High', color: '#ff9f43', radiusMeters: 560 },
  { name: 'Medium', color: '#f3c969', radiusMeters: 470 },
  { name: 'Low', color: '#5bc99b', radiusMeters: 410 },
]

export const areas: Area[] = [
  { id: 'AR-01', name: 'Zone Alpha', lat: 19.076, lng: 72.877, population: 12400, severity: 5, injured: 184, trapped: 62, requests: 47, priority: 'Critical', score: 94 },
  { id: 'AR-02', name: 'Zone Bravo', lat: 19.105, lng: 72.854, population: 8900, severity: 4, injured: 112, trapped: 35, requests: 31, priority: 'High', score: 82 },
  { id: 'AR-03', name: 'Zone Charlie', lat: 19.045, lng: 72.91, population: 6700, severity: 4, injured: 86, trapped: 21, requests: 28, priority: 'High', score: 76 },
  { id: 'AR-04', name: 'Zone Delta', lat: 19.13, lng: 72.9, population: 5200, severity: 3, injured: 48, trapped: 12, requests: 18, priority: 'Medium', score: 61 },
  { id: 'AR-05', name: 'Zone Echo', lat: 19.02, lng: 72.84, population: 3800, severity: 2, injured: 24, trapped: 4, requests: 12, priority: 'Medium', score: 48 },
  { id: 'AR-06', name: 'Zone Foxtrot', lat: 19.16, lng: 72.87, population: 2700, severity: 2, injured: 15, trapped: 3, requests: 8, priority: 'Low', score: 32 },
  { id: 'AR-07', name: 'Zone Golf', lat: 19.065, lng: 72.82, population: 6100, severity: 4, injured: 73, trapped: 18, requests: 22, priority: 'High', score: 73 },
  { id: 'AR-08', name: 'Zone Hotel', lat: 19.11, lng: 72.93, population: 1900, severity: 1, injured: 9, trapped: 1, requests: 5, priority: 'Low', score: 24 },
  { id: 'AR-09', name: 'Zone India', lat: 19.0, lng: 72.89, population: 7400, severity: 5, injured: 132, trapped: 41, requests: 36, priority: 'Critical', score: 89 },
  { id: 'AR-10', name: 'Zone Juliet', lat: 19.145, lng: 72.83, population: 4300, severity: 3, injured: 39, trapped: 8, requests: 14, priority: 'Medium', score: 54 },
]

export const resources: { id: ResourceId; name: string; available: number; total: number; unit: string; icon: 'ambulance' | 'teams' | 'medical' | 'food' | 'water' | 'shelter' | 'transport' }[] = [
  { id: 'ambulances', name: 'Ambulances', available: 24, total: 42, unit: 'vehicles', icon: 'ambulance' },
  { id: 'rescue-teams', name: 'Rescue teams', available: 18, total: 26, unit: 'teams', icon: 'teams' },
  { id: 'medical-kits', name: 'Medical kits', available: 1240, total: 2200, unit: 'kits', icon: 'medical' },
  { id: 'food-kits', name: 'Food kits', available: 1780, total: 2600, unit: 'kits', icon: 'food' },
  { id: 'water-units', name: 'Water units', available: 920, total: 1500, unit: 'units', icon: 'water' },
  { id: 'shelter-capacity', name: 'Shelter capacity', available: 680, total: 1200, unit: 'beds', icon: 'shelter' },
  { id: 'emergency-transport', name: 'Emergency transport', available: 12, total: 20, unit: 'vehicles', icon: 'transport' },
]

export const emergencyRequests: {
  id: string
  areaId: string
  type: RequestType
  severity: Priority
  count: number
  status: RequestStatus
  timestamp: string
}[] = [
  { id: 'RQ-001', areaId: 'AR-01', type: 'Medical', severity: 'Critical', count: 12, status: 'Pending', timestamp: '11:18' },
  { id: 'RQ-002', areaId: 'AR-01', type: 'Rescue', severity: 'Critical', count: 15, status: 'Processing', timestamp: '11:11' },
  { id: 'RQ-003', areaId: 'AR-01', type: 'Water', severity: 'High', count: 20, status: 'Assigned', timestamp: '10:56' },
  { id: 'RQ-004', areaId: 'AR-02', type: 'Medical', severity: 'High', count: 8, status: 'Pending', timestamp: '11:21' },
  { id: 'RQ-005', areaId: 'AR-02', type: 'Food', severity: 'Medium', count: 23, status: 'Processing', timestamp: '10:50' },
  { id: 'RQ-006', areaId: 'AR-03', type: 'Rescue', severity: 'High', count: 5, status: 'Pending', timestamp: '11:14' },
  { id: 'RQ-007', areaId: 'AR-03', type: 'Water', severity: 'Medium', count: 23, status: 'Completed', timestamp: '10:38' },
  { id: 'RQ-008', areaId: 'AR-04', type: 'Medical', severity: 'Medium', count: 3, status: 'Pending', timestamp: '11:06' },
  { id: 'RQ-009', areaId: 'AR-04', type: 'Shelter', severity: 'Medium', count: 15, status: 'Processing', timestamp: '10:52' },
  { id: 'RQ-010', areaId: 'AR-05', type: 'Food', severity: 'Medium', count: 2, status: 'Pending', timestamp: '11:03' },
  { id: 'RQ-011', areaId: 'AR-05', type: 'Shelter', severity: 'Low', count: 10, status: 'Completed', timestamp: '10:20' },
  { id: 'RQ-012', areaId: 'AR-06', type: 'Water', severity: 'Low', count: 8, status: 'Completed', timestamp: '10:17' },
  { id: 'RQ-013', areaId: 'AR-07', type: 'Evacuation', severity: 'High', count: 1, status: 'Pending', timestamp: '11:25' },
  { id: 'RQ-014', areaId: 'AR-07', type: 'Medical', severity: 'High', count: 21, status: 'Assigned', timestamp: '10:47' },
  { id: 'RQ-015', areaId: 'AR-08', type: 'Shelter', severity: 'Low', count: 5, status: 'Completed', timestamp: '10:02' },
  { id: 'RQ-016', areaId: 'AR-09', type: 'Medical', severity: 'Critical', count: 2, status: 'Pending', timestamp: '11:28' },
  { id: 'RQ-017', areaId: 'AR-09', type: 'Rescue', severity: 'Critical', count: 34, status: 'Processing', timestamp: '11:01' },
  { id: 'RQ-018', areaId: 'AR-10', type: 'Medical', severity: 'Medium', count: 1, status: 'Pending', timestamp: '10:59' },
  { id: 'RQ-019', areaId: 'AR-10', type: 'Water', severity: 'Low', count: 13, status: 'Completed', timestamp: '10:30' },
]

export const alerts = [
  { id: 'AL-001', level: 'critical', title: 'Critical area in demo data', detail: 'Zone Alpha · Sample priority score 94', time: '2 min ago', unread: true },
  { id: 'AL-002', level: 'warning', title: 'Sample resource threshold', detail: 'Medical kit demo availability is below 60%', time: '14 min ago', unread: true },
  { id: 'AL-003', level: 'info', title: 'Sample request group added', detail: '2 pending medical requests from Zone India', time: '28 min ago', unread: true },
]

export const recommendations = [
  { areaId: 'AR-01', allocation: [{ resourceId: 'ambulances' as ResourceId, count: 8 }, { resourceId: 'rescue-teams' as ResourceId, count: 4 }, { resourceId: 'medical-kits' as ResourceId, count: 240 }], explanation: 'High sample severity, affected population, and trapped-person counts are shown for officer review.' },
  { areaId: 'AR-09', allocation: [{ resourceId: 'ambulances' as ResourceId, count: 6 }, { resourceId: 'rescue-teams' as ResourceId, count: 3 }, { resourceId: 'medical-kits' as ResourceId, count: 180 }], explanation: 'Sample injury and emergency-request counts are shown for officer review.' },
]

export const resourceCenters = [
  { id: 'RC-01', name: 'North Ridge Resource Center', lat: 19.15, lng: 72.88, resourceIds: ['ambulances', 'rescue-teams'] as ResourceId[] },
  { id: 'RC-02', name: 'East Valley Resource Center', lat: 19.12, lng: 72.94, resourceIds: ['medical-kits', 'food-kits'] as ResourceId[] },
  { id: 'RC-03', name: 'Central Field Resource Center', lat: 19.075, lng: 72.86, resourceIds: ['ambulances', 'water-units'] as ResourceId[] },
  { id: 'RC-04', name: 'South Gate Resource Center', lat: 19.015, lng: 72.865, resourceIds: ['shelter-capacity', 'emergency-transport'] as ResourceId[] },
  { id: 'RC-05', name: 'West Point Resource Center', lat: 19.055, lng: 72.815, resourceIds: ['rescue-teams', 'medical-kits'] as ResourceId[] },
]

export const priorityDistribution = priorityLevels.map(({ name, color }) => ({
  name,
  color,
  count: areas.filter((area) => area.priority === name).length,
}))

export function getDashboardMetrics() {
  const resourceAvailability = Object.fromEntries(resources.map((resource) => [resource.id, resource])) as Record<ResourceId, (typeof resources)[number]>
  const pendingRequests = emergencyRequests.filter((request) => request.status === 'Pending')
  const criticalAreaIds = new Set(areas.filter((area) => area.priority === 'Critical').map((area) => area.id))
  const criticalPendingRequestCount = pendingRequests
    .filter((request) => criticalAreaIds.has(request.areaId))
    .reduce((total, request) => total + request.count, 0)

  return {
    criticalAreas: areas.filter((area) => area.priority === 'Critical').length,
    highPriorityAreas: areas.filter((area) => area.priority === 'High').length,
    peopleAffected: areas.reduce((total, area) => total + area.population, 0),
    availableAmbulances: resourceAvailability.ambulances.available,
    totalAmbulances: resourceAvailability.ambulances.total,
    availableRescueTeams: resourceAvailability['rescue-teams'].available,
    totalRescueTeams: resourceAvailability['rescue-teams'].total,
    medicalKits: resourceAvailability['medical-kits'].available,
    shelterCapacity: resourceAvailability['shelter-capacity'].available,
    pendingRequests: pendingRequests.reduce((total, request) => total + request.count, 0),
    pendingCriticalRequests: criticalPendingRequestCount,
    areaCount: areas.length,
    resourceCenterCount: resourceCenters.length,
    unreadAlerts: alerts.filter((alert) => alert.unread).length,
  }
}

export function getAreaForRecommendation(areaId: string) {
  return areas.find((area) => area.id === areaId)
}

export function formatRecommendationAllocation(items: (typeof recommendations)[number]['allocation']) {
  const resourceNames = new Map(resources.map((resource) => [resource.id, resource.name]))
  return items.map((item) => `${item.count.toLocaleString()} ${resourceNames.get(item.resourceId) ?? item.resourceId}`).join(' · ')
}
