import { useEffect, useMemo, useState } from 'react'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Search } from 'lucide-react'
import { api } from '../services/api'
import { areas, priorityLevels, resourceCenters, type Priority } from '../data/demo'

type Layers = {
  incidents: { id:number; source_key:string|null; hazard_type:string; title:string; severity:string|null; latitude:number|null; longitude:number|null; source_published_at:string|null; source_url:string|null; is_official_warning:boolean }[]
  weather: { id:number; source_key:string|null; variable:string; value:number; unit:string; observed_at:string; latitude:number|null; longitude:number|null; quality_status:string; source_attribution:string|null }[]
  resource_centers: { id:number; name:string; latitude:number; longitude:number; is_demo:boolean }[]
  affected_areas: { area_id:string; name:string; latitude:number; longitude:number; priority_class:string; priority_score:number; is_demo:boolean }[]
}

function DemoAreaMarker({ area }: { area: typeof areas[number] }) {
  const level = priorityLevels.find(item => item.name === area.priority)
  const color = level?.color ?? '#9AAAB9'
  return <Circle center={[area.lat, area.lng]} radius={level?.radiusMeters ?? 450} pathOptions={{ color, fillColor: color, fillOpacity: .13, weight: 1.4 }}><Popup><div className="map-popup"><b>{area.name}</b><span>{area.priority} sample class · score {area.score}</span><span>{area.population.toLocaleString()} people in sample data</span><span className="popup-coord">ILLUSTRATIVE DEMO AREA · {area.id}</span></div></Popup></Circle>
}

function FitPoints({ points }: { points: [number,number][] }) {
  const map = useMap()
  useEffect(() => { if (points.length) map.fitBounds(L.latLngBounds(points), { padding: [25, 25], maxZoom: 11 }) }, [map, points])
  return null
}

export function IntegratedMap({ compact = false }: { compact?: boolean }) {
  const [mode, setMode] = useState<'integrated'|'demo'>('integrated')
  const [query, setQuery] = useState('')
  const [priority, setPriority] = useState<Priority|'All'>('All')
  const [hazard, setHazard] = useState('All')
  const [source, setSource] = useState('All')
  const [severity, setSeverity] = useState('All')
  const [state, setState] = useState('')
  const [district, setDistrict] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [data, setData] = useState<Layers|null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    if (mode === 'demo') return
    let active = true
    const params = new URLSearchParams()
    if (hazard !== 'All') params.set('hazard_type', hazard)
    if (source !== 'All') params.set('source_key', source)
    if (severity !== 'All') params.set('severity', severity)
    if (state.trim()) params.set('state', state.trim())
    if (district.trim()) params.set('district', district.trim())
    if (startDate) params.set('start_at', new Date(`${startDate}T00:00:00Z`).toISOString())
    if (endDate) params.set('end_at', new Date(`${endDate}T23:59:59.999Z`).toISOString())
    api<Layers>(`/v1/map/layers${params.size ? `?${params}` : ''}`).then(value => { if (active) { setData(value); setError('') } }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Integrated map data is unavailable') })
    return () => { active = false }
  }, [mode, hazard, source, severity, state, district, startDate, endDate])

  const demoAreas = useMemo(() => areas.filter(area => (priority === 'All' || area.priority === priority) && area.name.toLowerCase().includes(query.toLowerCase())), [priority, query])
  const incidents = (data?.incidents ?? []).filter(item => item.latitude !== null && item.longitude !== null && `${item.title} ${item.hazard_type}`.toLowerCase().includes(query.toLowerCase()))
  const weather = (data?.weather ?? []).filter(item => item.latitude !== null && item.longitude !== null && `${item.variable} ${item.source_key ?? ''}`.toLowerCase().includes(query.toLowerCase()))
  const reviewedAreas = (data?.affected_areas ?? []).filter(item => !item.is_demo && item.name.toLowerCase().includes(query.toLowerCase()))
  const centers = (data?.resource_centers ?? []).filter(item => !item.is_demo)
  const demoCenter: [number,number] = useMemo(() => [areas.reduce((sum,item) => sum + item.lat, 0) / areas.length, areas.reduce((sum,item) => sum + item.lng, 0) / areas.length], [])
  const points: [number,number][] = mode === 'demo' ? demoAreas.map(item => [item.lat,item.lng]) : [
    ...incidents.map(item => [item.latitude!,item.longitude!] as [number,number]),
    ...weather.map(item => [item.latitude!,item.longitude!] as [number,number]),
    ...reviewedAreas.map(item => [item.latitude,item.longitude] as [number,number]),
    ...centers.map(item => [item.latitude,item.longitude] as [number,number]),
  ]
  const mappedCount = incidents.length + weather.length + reviewedAreas.length + centers.length

  return <div className={`map-frame ${compact ? 'map-compact' : ''}`} aria-label={mode === 'demo' ? 'Illustrative demo map' : 'Integrated source data map'}>
    <MapContainer center={mode === 'demo' ? demoCenter : [17.385,78.486]} zoom={mode === 'demo' ? 11 : 5} scrollWheelZoom={false} zoomControl={!compact} className="leaflet-map">
      <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><FitPoints points={points}/>
      {mode === 'demo' && demoAreas.map(area => <DemoAreaMarker key={area.id} area={area}/>)}
      {mode === 'demo' && resourceCenters.map(center => <CircleMarker key={center.id} center={[center.lat,center.lng]} radius={6} pathOptions={{color:'#55A8F5',fillColor:'#55A8F5',fillOpacity:.9}}><Popup><div className="map-popup"><b>{center.name}</b><span>Illustrative resource center</span></div></Popup></CircleMarker>)}
      {mode === 'integrated' && incidents.map(item => <CircleMarker key={item.id} center={[item.latitude!,item.longitude!]} radius={8} pathOptions={{color:item.is_official_warning?'#EF5350':'#FF9F43',fillColor:item.is_official_warning?'#EF5350':'#FF9F43',fillOpacity:.85}}><Popup><div className="map-popup"><b>{item.title}</b><span>{item.hazard_type} · {item.severity ?? 'severity unavailable'}</span><span>{item.is_official_warning?'Official warning':'External event'} · {item.source_key}</span><span>{item.source_published_at ? new Date(item.source_published_at).toLocaleString() : 'No source timestamp'}</span>{item.source_url && <a href={item.source_url} target="_blank" rel="noreferrer">Open source record</a>}</div></Popup></CircleMarker>)}
      {mode === 'integrated' && weather.map(item => <CircleMarker key={item.id} center={[item.latitude!,item.longitude!]} radius={6} pathOptions={{color:'#55A8F5',fillColor:'#55A8F5',fillOpacity:.85}}><Popup><div className="map-popup"><b>{item.variable}</b><span>{item.value} {item.unit}</span><span>{new Date(item.observed_at).toLocaleString()} · {item.source_attribution ?? item.source_key}</span><span>{item.quality_status}</span></div></Popup></CircleMarker>)}
      {mode === 'integrated' && reviewedAreas.map(item => <CircleMarker key={item.area_id} center={[item.latitude,item.longitude]} radius={7} pathOptions={{color:'#32C99A',fillColor:'#32C99A',fillOpacity:.4}}><Popup><div className="map-popup"><b>{item.name}</b><span>{item.priority_class} reviewed area · score {item.priority_score}</span></div></Popup></CircleMarker>)}
      {mode === 'integrated' && centers.map(item => <CircleMarker key={item.id} center={[item.latitude,item.longitude]} radius={6} pathOptions={{color:'#22D3EE',fillColor:'#22D3EE',fillOpacity:.9}}><Popup><b>{item.name}</b></Popup></CircleMarker>)}
    </MapContainer>
    <div className="map-toolbar"><label className="map-search"><Search size={14}/><input aria-label="Search mapped records" placeholder="Search current map data…" value={query} onChange={event => setQuery(event.target.value)}/></label><div className="map-mode-toggle" role="group" aria-label="Map data mode"><button type="button" className={mode==='integrated'?'selected':''} aria-pressed={mode==='integrated'} onClick={() => setMode('integrated')}>Integrated</button><button type="button" className={mode==='demo'?'selected':''} aria-pressed={mode==='demo'} onClick={() => setMode('demo')}>Demo preview</button></div></div>
    {mode === 'integrated' && <div className="map-filter-row"><label>Hazard<select aria-label="Filter hazard type" value={hazard} onChange={event => setHazard(event.target.value)}><option>All</option><option value="earthquake">Earthquake</option><option value="flood">Flood</option><option value="tropical_cyclone">Tropical cyclone</option></select></label><label>Severity<select aria-label="Filter severity" value={severity} onChange={event => setSeverity(event.target.value)}><option>All</option>{['Extreme','Severe','Moderate','Minor','red','orange','green'].map(item=><option key={item}>{item}</option>)}</select></label><label>Source<select aria-label="Filter data source" value={source} onChange={event => setSource(event.target.value)}><option>All</option><option value="usgs_earthquakes">USGS</option><option value="gdacs_events">GDACS</option><option value="sachet_cap">SACHET</option><option value="nwic_telangana_rainfall">NWIC Telangana</option></select></label><label>State code<input aria-label="Filter state code" placeholder="e.g. TS" value={state} onChange={event=>setState(event.target.value)}/></label><label>District code<input aria-label="Filter district code" placeholder="e.g. HYD" value={district} onChange={event=>setDistrict(event.target.value)}/></label><label>From date<input aria-label="Filter start date" type="date" value={startDate} onChange={event=>setStartDate(event.target.value)}/></label><label>To date<input aria-label="Filter end date" type="date" value={endDate} onChange={event=>setEndDate(event.target.value)}/></label></div>}
    <div className="map-legend">{mode === 'demo' ? <><div className="legend-title">SAMPLE PRIORITY · FILTER</div>{priorityLevels.map(({name,color}) => <button type="button" className={`legend-item ${priority===name?'legend-active':''}`} key={name} onClick={() => setPriority(priority===name?'All':name)} aria-pressed={priority===name}><i style={{background:color}}/>{name}</button>)}</> : <><div className="legend-title">INGESTED RECORDS ONLY</div><span className="legend-item"><i style={{background:'#EF5350'}}/>Official warning</span><span className="legend-item"><i style={{background:'#FF9F43'}}/>Event</span><span className="legend-item"><i style={{background:'#55A8F5'}}/>Observation</span></>}</div>
    <div className="map-attribution-note">{mode === 'demo' ? 'Illustrative demo locations' : 'Integrated records · source timestamps in details'}</div>
    {!compact && <div className="map-side-panel"><div className="map-side-head"><div><span className="eyebrow">{mode==='demo'?'DEMO AREAS':'INGESTED RECORDS'}</span><h3>{mode==='demo' ? `${demoAreas.length} illustrative areas` : `${mappedCount} mapped records`}</h3></div></div><div className="map-area-list">{mode==='demo' ? demoAreas.map(area => <div className="map-area-item" key={area.id}><span className={`status-dot ${area.priority.toLowerCase()}-dot`}/><span className="map-area-copy"><b>{area.name}</b><small>Illustrative demo area · {area.id}</small></span></div>) : error ? <div className="map-empty-state" role="alert">{error}</div> : mappedCount===0 ? <div className="map-empty-state" role="status">No integrated records match these filters. Demo locations are separate under Demo preview.</div> : <>{incidents.map(item => <div className="map-area-item" key={`i-${item.id}`}><span className={`status-dot ${item.is_official_warning?'critical-dot':'high-dot'}`}/><span className="map-area-copy"><b>{item.title}</b><small>{item.source_key} · {item.source_published_at ? new Date(item.source_published_at).toLocaleString() : 'timestamp unavailable'}</small></span></div>)}{weather.map(item => <div className="map-area-item" key={`w-${item.id}`}><span className="status-dot low-dot"/><span className="map-area-copy"><b>{item.variable}: {item.value} {item.unit}</b><small>{item.source_key} · {new Date(item.observed_at).toLocaleString()}</small></span></div>)}</>}</div><div className="map-centers-label">{mode==='demo' ? `${resourceCenters.length} illustrative centers` : `${centers.length} verified centers`}</div></div>}
  </div>
}
