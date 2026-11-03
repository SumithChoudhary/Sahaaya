import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Activity, Ambulance, AlertTriangle, ArrowRight, ArrowUpRight, Bell, Boxes, BrainCircuit, Check, ChevronDown, CircleHelp, ClipboardList, Clock3, Command, FileBarChart2, Flame, Gauge, HeartPulse, History, LayoutDashboard, LifeBuoy, LogOut, Map as MapIcon, Menu, Package, Radio, RefreshCw, Search, Settings, Shield, ShieldAlert, Siren, SlidersHorizontal, Sparkles, TentTree, Truck, Users, Waves, X } from 'lucide-react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { alerts, areas, demoIncident, formatRecommendationAllocation, getAreaForRecommendation, getDashboardMetrics, priorityDistribution, priorityLevels, recommendations, resourceCenters, resources, type Priority } from './data/demo'
import { demoUser, getGreeting, getUserInitials } from './data/auth'
import { Button } from './components/ui/button'
import { api, clearSession, getSessionUser, login, type AlertRecord, type AreaRecord, type RequestRecord, type ResourceRecord, type User } from './services/api'
import { OperationsPage } from './pages/OperationsPages'

const navGroups = [
  { label: 'COMMAND', items: [{ to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard }, { to: '/map', label: 'Disaster map', icon: MapIcon }, { to: '/areas', label: 'Affected areas', icon: Waves }, { to: '/ai-priorities', label: 'AI priorities', icon: BrainCircuit }] },
  { label: 'OPERATIONS', items: [{ to: '/resources', label: 'Resources', icon: Boxes }, { to: '/requests', label: 'Emergency requests', icon: ClipboardList }, { to: '/optimization', label: 'Optimization', icon: Gauge }, { to: '/analytics', label: 'Analytics', icon: FileBarChart2 }, { to: '/deployments', label: 'Deployments', icon: Truck }, { to: '/alerts', label: 'Alerts', icon: Bell }] },
  { label: 'REVIEW & CONFIGURE', items: [{ to: '/simulation', label: 'Simulation', icon: SlidersHorizontal }, { to: '/history', label: 'History', icon: History }, { to: '/reports', label: 'Reports', icon: ClipboardList }, { to: '/settings', label: 'Settings', icon: Settings }] },
]

function App() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sessionUser] = useState<User | null>(() => getSessionUser())
  const location = useLocation()
  const dashboard = location.pathname === '/dashboard'
  const sidebarRef = useRef<HTMLElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (mobileOpen) sidebarRef.current?.querySelector<HTMLAnchorElement>('.nav-link')?.focus()
    else if (window.matchMedia('(max-width: 800px)').matches) menuButtonRef.current?.focus()
  }, [mobileOpen])

  useEffect(() => {
    if (!mobileOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileOpen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [mobileOpen])

  return <div className="app-shell">
    {location.pathname !== '/' && location.pathname !== '/login' && <>
      {mobileOpen && <button className="scrim" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
      {!sessionUser && <Navigate to="/login" replace />}
      <aside ref={sidebarRef} id="primary-sidebar" className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
        <Link to="/dashboard" className="brand" aria-label="Sahaaya dashboard"><div className="brand-mark"><Command size={19} strokeWidth={2.2} /></div><span>SAHA<span className="brand-ai">AYA</span></span></Link>
        <div className="side-caption">EMERGENCY OPERATIONS</div>
        <div className="incident-mini"><div className="incident-icon"><Siren size={16} /></div><div><strong>{demoIncident.title}</strong><span><i className="live-dot" /> Demo scenario</span></div><ChevronDown size={15} className="incident-chevron" /></div>
        <nav className="side-nav" aria-label="Primary navigation">{navGroups.map(group => <section key={group.label} className="nav-group"><div className="nav-heading">{group.label}</div>{group.items.map(({ to, label, icon: Icon }) => <Link key={to} to={to} onClick={() => setMobileOpen(false)} className={`nav-link ${location.pathname === to ? 'active' : ''}`} aria-current={location.pathname === to ? 'page' : undefined}><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{label === 'Alerts' && getDashboardMetrics().unreadAlerts > 0 && <span className="nav-badge" aria-label={`${getDashboardMetrics().unreadAlerts} unread alerts`}>{getDashboardMetrics().unreadAlerts}</span>}</Link>)}</section>)}</nav>
        <div className="sidebar-bottom"><div className="support-link"><CircleHelp size={16} /><span>Help & documentation</span><ArrowUpRight size={13} /></div><div className="profile-row"><UserAvatar name={sessionUser?.name ?? demoUser.name}/><div className="profile-text"><strong>{sessionUser?.name ?? demoUser.name}</strong><span>{sessionUser?.role ?? demoUser.role}</span></div><Link className="icon-button profile-menu" aria-label="Sign out" title="Sign out" to="/login" onClick={()=>clearSession()}><LogOut size={16}/></Link></div></div>
      </aside>
      <main className="main-area"><header className="topbar"><button ref={menuButtonRef} className="icon-button mobile-menu" onClick={() => setMobileOpen(true)} aria-label="Open navigation" aria-expanded={mobileOpen} aria-controls="primary-sidebar"><Menu size={19} /></button><div className="breadcrumb"><span>Operations</span><span className="crumb-slash">/</span><strong>{dashboard ? 'Dashboard' : titleForPath(location.pathname)}</strong></div><div className="topbar-right"><div className="top-live"><i className="live-dot" />Demo environment</div><Link to="/alerts" className="icon-button notification-button" aria-label={`Open alerts, ${getDashboardMetrics().unreadAlerts} unread`}><Bell size={17} /><i /></Link><div className="top-divider" /><div className="top-user" aria-label={`Signed in as ${sessionUser?.name ?? demoUser.name}, ${sessionUser?.role ?? demoUser.role}`}><UserAvatar small name={sessionUser?.name ?? demoUser.name}/><span>{sessionUser?.name ?? demoUser.name}</span><ChevronDown size={14} aria-hidden="true" /></div></div></header><div className="page-content"><Routes><Route path="/dashboard" element={<Dashboard userName={sessionUser?.name ?? demoUser.name} />} />{navGroups.flatMap(g => g.items).filter(x => x.to !== '/dashboard').map(x => <Route key={x.to} path={x.to} element={x.to==='/map'?<SectionPage title={x.label}/>:<OperationsPage title={x.label} path={x.to}/>} />)}<Route path="*" element={<Navigate to="/dashboard" replace />} /></Routes></div></main>
    </>}
    <Routes><Route path="/" element={<Landing />} /><Route path="/login" element={<Login />} /></Routes>
  </div>
}

function titleForPath(path: string) { return navGroups.flatMap(g => g.items).find(x => x.to === path)?.label ?? 'Dashboard' }

function UserAvatar({ small = false, name = demoUser.name }: { small?: boolean; name?: string }) {
  return <div className={`avatar ${small ? 'avatar-small' : ''}`} aria-hidden="true">{getUserInitials(name)}</div>
}

function Landing() {
  return <div className="landing"><header className="landing-nav"><Link to="/" className="brand" aria-label="Sahaaya home"><div className="brand-mark"><Command size={19} /></div><span>SAHA<span className="brand-ai">AYA</span></span></Link><div className="landing-nav-links"><a href="#platform">Platform</a><a href="#workflow">How it works</a><a href="#capabilities">Capabilities</a></div><div className="landing-actions"><Link to="/login" className="login-link">Sign in</Link><Link to="/dashboard" className="button button-primary button-small">Launch command center <ArrowRight size={15} /></Link></div></header>
    <section className="hero"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-pulse" /> DISASTER RESPONSE INTELLIGENCE</div><h1>Make every<br />resource <em>count.</em></h1><p className="brand-tagline">Intelligent Prioritization. Optimized Resources. Coordinated Response.</p><p className="hero-description">A software decision-support prototype for human-reviewed resource planning. Explore a synthetic priority model, transparent demand estimates, and a custom Genetic Algorithm using fictional demo data.</p><div className="hero-buttons"><Link to="/dashboard" className="button button-primary">Launch command center <ArrowRight size={16} /></Link><a href="#workflow" className="button button-quiet">Explore the platform <ArrowRight size={15} /></a></div><div className="hero-trust"><div className="trust-avatars"><span>EM</span><span>RO</span><span>+</span></div><span>Built to support emergency decision-makers</span></div></div>
      <div className="hero-visual"><div className="hero-grid" /><div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" /><div className="hero-signal"><div className="signal-center"><Command size={25} /></div><div className="signal-ring ring-a" /><div className="signal-ring ring-b" /><div className="signal-sweep" /></div><div className="hero-float float-critical"><span className="status-dot critical-dot" /><div><b>{areas.find((area) => area.priority === 'Critical')?.name ?? 'Demo area'}</b><small>Sample score · {areas.find((area) => area.priority === 'Critical')?.score ?? '—'}</small></div><ArrowUpRight size={15} /></div><div className="hero-float float-allocation"><div className="mini-icon"><BrainCircuit size={16} /></div><div><b>Sample recommendation</b><small>Fictional data · illustrative only</small></div><span className="tiny-check"><Check size={12} /></span></div><div className="hero-coord">ILLUSTRATIVE DEMO LOCATIONS</div></div>
    </section><div className="landing-ribbon"><span>DECISION SUPPORT FOR COMPLEX EMERGENCIES</span><div className="ribbon-lines"><i /><i /><i /><i /><i /><i /><i /></div><span>HUMAN AUTHORITIES STAY IN CONTROL</span></div>
    <section id="platform" className="landing-section problem-section"><div><div className="eyebrow">THE CHALLENGE</div><h2>Many urgent needs.<br /><span>Limited resources.</span></h2></div><div className="problem-copy"><p>When disaster strikes, multiple areas compete for the same finite ambulances, rescue teams, medical supplies, and shelter capacity.</p><p>Sahaaya helps authorities see where needs are greatest and compare resource allocation options with clarity.</p><div className="human-note"><Shield size={16} /><span>Recommendations support decisions. Authorities make them.</span></div></div></section>
    <section id="workflow" className="workflow-section"><div className="section-heading"><div><div className="eyebrow">DECISION SUPPORT WORKFLOW</div><h2>A clearer path through complexity.</h2><p className="workflow-note">Prototype services use fictional data, synthetic labels, and transparent demand heuristics.</p></div><span>01 — 06</span></div><div className="workflow-track">{[{n:'01',title:'Disaster data',sub:'Affected areas & requests',icon:Radio},{n:'02',title:'Priority model',sub:'Synthetic Random Forest demo',icon:BrainCircuit},{n:'03',title:'Demand estimate',sub:'Transparent prototype heuristic',icon:Activity},{n:'04',title:'Optimization',sub:'Custom Genetic Algorithm',icon:Sparkles},{n:'05',title:'Recommendations',sub:'Human review required',icon:Boxes},{n:'06',title:'Human decision',sub:'Review, change, decide',icon:Shield}].map(({n,title,sub,icon:Icon},i)=><div className="workflow-step" key={n}><div className={`workflow-icon ${i===5?'human-step':''}`}><Icon size={18}/></div><small>{n}</small><b>{title}</b><span>{sub}</span>{i<5&&<ArrowRight size={14} className="step-arrow"/>}</div>)}</div></section>
    <section id="capabilities" className="landing-section capabilities"><div><div className="eyebrow">BUILT FOR THE FIELD DESK</div><h2>Clarity for the<br />moments that matter.</h2></div><div className="capability-grid">{[{icon:BrainCircuit,title:'Priority prediction · demo model',copy:'Inspect a reproducible synthetic classifier, its feature signals, and limitations.'},{icon:Gauge,title:'Resource optimization · prototype GA',copy:'Explore a custom Genetic Algorithm under supply constraints and estimated response costs.'},{icon:Shield,title:'Human-led decisions',copy:'Authorities review, modify, approve, or reject every recommendation. No automatic dispatch.'},{icon:MapIcon,title:'Shared operational picture',copy:'Manage fictional incident zones, requests, and resource context in one workspace.'}].map(({icon:Icon,title,copy})=><article className="capability-card" key={title}><div className="capability-icon"><Icon size={19}/></div><h3>{title}</h3><p>{copy}</p><ArrowUpRight size={15} className="capability-arrow"/></article>)}</div></section>
    <footer className="landing-footer"><Link to="/" className="brand" aria-label="Sahaaya home"><div className="brand-mark"><Command size={17}/></div><span>SAHA<span className="brand-ai">AYA</span></span></Link><span>Intelligent Prioritization. Optimized Resources. Coordinated Response.</span><span>Smart Disaster Resource Allocation and Coordination Platform</span></footer>
  </div>
}

function Login() {
  const [error,setError]=useState(''), [busy,setBusy]=useState(false)
  async function submit(e:React.FormEvent<HTMLFormElement>){e.preventDefault();const data=new FormData(e.currentTarget);setBusy(true);setError('');try{await login(String(data.get('email')),String(data.get('password')));window.location.href='/dashboard'}catch(reason){setError(reason instanceof Error?reason.message:'Sign-in failed')}finally{setBusy(false)}}
  return <div className="login-screen"><div className="login-brand"><Link to="/" className="brand" aria-label="Sahaaya home"><div className="brand-mark"><Command size={19}/></div><span>SAHA<span className="brand-ai">AYA</span></span></Link></div><div className="login-card"><div className="login-icon"><Shield size={21}/></div><div className="eyebrow">DEMO ACCESS · ROLE-AWARE AUTHENTICATION</div><h1>Welcome, {demoUser.name.split(' ')[0]}</h1><p>Sign in to the fictional emergency officer command center.</p><form onSubmit={submit}><label>Email address<input name="email" type="email" autoComplete="username" placeholder="Demo email" defaultValue={demoUser.email} required /></label><label>Password<input name="password" type="password" autoComplete="current-password" placeholder="Demo password" defaultValue="demo-preview" required /></label>{error&&<p className="operation-error login-error" role="alert">{error}</p>}<Button variant="primary" className="login-submit" type="submit" disabled={busy}>{busy?'Signing in…':'Continue to command center'} <ArrowRight size={16}/></Button></form><div className="demo-login-note"><i className="live-dot"/> Demo credentials · API authentication enabled</div><small className="login-credential-hint">Officer: sumith@sahaaya.demo · demo-preview</small></div><div className="login-footer">SAHAAYA <span>·</span> Smart Disaster Resource Allocation and Coordination Platform</div></div>
}

function Dashboard({userName=demoUser.name}:{userName?:string}) {
  const [updated, setUpdated] = useState(new Date())
  const [apiData, setApiData] = useState<{areas:AreaRecord[];resources:ResourceRecord[];requests:RequestRecord[];alerts:AlertRecord[];centers:{id:number}[]}|null>(null)
  const [apiIssue, setApiIssue] = useState('')
  async function refreshData(){try{const [areaData,resourceData,requestData,alertData,centerData]=await Promise.all([api<AreaRecord[]>('/areas'),api<ResourceRecord[]>('/resources'),api<RequestRecord[]>('/requests'),api<AlertRecord[]>('/alerts'),api<{id:number}[]>('/resource-centers')]);setApiData({areas:areaData,resources:resourceData,requests:requestData,alerts:alertData,centers:centerData});setApiIssue('')}catch(e){setApiIssue(e instanceof Error?e.message:'API unavailable; showing centralized static demo data')}}
  useEffect(()=>{void refreshData()},[])
  const timeString = updated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  const demoMetrics = getDashboardMetrics()
  const resourceValue=(key:string,field:'available'|'total')=>apiData?.resources.find(item=>item.resource_key===key)?.[field]
  const metrics = apiData ? {
    ...demoMetrics,
    criticalAreas:apiData.areas.filter(a=>a.priority_class==='Critical').length,
    highPriorityAreas:apiData.areas.filter(a=>a.priority_class==='High').length,
    peopleAffected:apiData.areas.reduce((n,a)=>n+a.population_affected,0),
    availableAmbulances:resourceValue('ambulances','available')??0,totalAmbulances:resourceValue('ambulances','total')??0,
    availableRescueTeams:resourceValue('rescue-teams','available')??0,totalRescueTeams:resourceValue('rescue-teams','total')??0,
    medicalKits:resourceValue('medical-kits','available')??0,shelterCapacity:resourceValue('shelter-capacity','available')??0,
    pendingRequests:apiData.requests.filter(r=>r.status==='Pending').reduce((n,r)=>n+r.people_affected,0),
    pendingCriticalRequests:apiData.requests.filter(r=>r.status==='Pending'&&r.severity==='Critical').reduce((n,r)=>n+r.people_affected,0),
    areaCount:apiData.areas.length,resourceCenterCount:apiData.centers.length,unreadAlerts:apiData.alerts.filter(a=>!a.is_read).length,
  } : demoMetrics
  const shownPriorityDistribution=apiData ? priorityLevels.map(({name,color})=>({name,color,count:apiData.areas.filter(a=>a.priority_class===name).length})) : priorityDistribution
  const displayedResources=apiData?apiData.resources.filter(item=>['ambulances','rescue-teams','medical-kits','shelter-capacity'].includes(item.resource_key)).map(item=>({...resources.find(resource=>resource.id===item.resource_key)!,name:item.name,available:item.available,total:item.total,unit:item.unit})):resources.filter((resource) => ['ambulances', 'rescue-teams', 'medical-kits', 'shelter-capacity'].includes(resource.id))
  const displayedAlerts=apiData?apiData.alerts.slice(0,3).map(item=>({id:item.alert_id,level:item.severity.toLowerCase(),title:item.title,detail:item.message,time:new Date(item.timestamp).toLocaleString(),unread:!item.is_read})):alerts
  const kpis = [
    { label: 'Critical areas', value: metrics.criticalAreas.toString().padStart(2, '0'), foot: 'From sample area priorities', icon: ShieldAlert, color:'red' },
    { label: 'High priority areas', value: metrics.highPriorityAreas.toString().padStart(2, '0'), foot: `Across ${metrics.areaCount} demo areas`, icon: Flame, color:'orange' },
    { label: 'People affected', value: new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(metrics.peopleAffected), foot: 'Sum across demo areas', icon: Users, color:'blue' },
    { label: 'Available ambulances', value: metrics.availableAmbulances.toLocaleString(), foot: `Of ${metrics.totalAmbulances.toLocaleString()} demo units`, icon: Ambulance, color:'green' },
    { label: 'Available rescue teams', value: metrics.availableRescueTeams.toLocaleString(), foot: `Of ${metrics.totalRescueTeams.toLocaleString()} demo teams`, icon: LifeBuoy, color:'violet' },
    { label: 'Medical supplies', value: metrics.medicalKits.toLocaleString(), foot: 'Demo kits available', icon: HeartPulse, color:'pink' },
    { label: 'Shelter capacity', value: metrics.shelterCapacity.toLocaleString(), foot: 'Demo beds available', icon: TentTree, color:'teal' },
    { label: 'Pending requests', value: metrics.pendingRequests.toLocaleString(), foot: `${metrics.pendingCriticalRequests.toLocaleString()} across critical demo areas`, icon: ClipboardList, color:'amber' },
  ]
  return <>
    <div className="page-heading"><div><div className="eyebrow">{demoIncident.label}</div><h1>{getGreeting(updated)}, {userName} <span className="wave" aria-hidden="true">✳</span></h1><p>Review this illustrative operational picture. It does not represent a live emergency.</p></div><div className="heading-actions"><span className="incident-status"><i className="live-dot"/> {demoIncident.state}</span><button className="button button-outline" onClick={()=>{setUpdated(new Date());void refreshData()}}><RefreshCw size={15}/> Refresh demo view</button></div></div>
    <div className="context-strip"><div><span className="context-label">LOCAL TIME</span><strong>{updated.toLocaleDateString([], {weekday:'short',day:'numeric',month:'short'})} <i>·</i> {timeString}</strong></div><div><span className="context-label">DATA STATUS</span><strong><i className="green-status-dot"/> {apiData?'Local API demo data':'Static demo fallback'} · Viewed {timeString}</strong></div><div className="context-disclaimer"><Shield size={14}/> {apiIssue||demoIncident.disclaimer}</div></div>
    <section className="kpi-grid" aria-label="Demo operational indicators">{kpis.map(({label,value,foot,icon:Icon,color})=><article key={label} className="kpi-card"><div className="kpi-top"><span>{label}</span><div className={`kpi-icon ${color}`}><Icon size={17}/></div></div><div className="kpi-value">{value}</div><div className="kpi-foot"><span>{foot}</span></div></article>)}</section>
    <section className="dashboard-grid map-row"><article className="panel map-panel"><div className="panel-header"><div><h2>Operational map</h2><p>Affected areas & illustrative resource centers</p></div><Link to="/map" className="text-link">Full map <ArrowUpRight size={14}/></Link></div><OperationalMap compact /></article><article className="panel priority-panel"><div className="panel-header"><div><h2>Priority distribution</h2><p>{apiData?'Synthetic model outputs':'Centralized sample labels'}</p></div><Link to="/ai-priorities" className="icon-button" aria-label="Open AI priorities"><ArrowUpRight size={16}/></Link></div><div className="priority-chart" role="img" aria-label={`Priority distribution across ${metrics.areaCount} demo areas`}><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={shownPriorityDistribution} dataKey="count" nameKey="name" innerRadius="66%" outerRadius="88%" paddingAngle={5} stroke="none">{shownPriorityDistribution.map((entry)=><Cell key={entry.name} fill={entry.color}/>)}</Pie><Tooltip contentStyle={{background:'#171f28',border:'1px solid #2a343e',borderRadius:8,color:'#eff3f7'}} itemStyle={{color:'#eff3f7'}}/></PieChart></ResponsiveContainer><div className="chart-center"><b>{metrics.areaCount}</b><span>DEMO AREAS</span></div></div><div className="priority-legend">{shownPriorityDistribution.map(p=><div key={p.name}><i style={{background:p.color}}/><span>{p.name}</span><b>{p.count.toString().padStart(2,'0')}</b></div>)}</div><Link to="/ai-priorities" className="panel-bottom-link">View demo priority analysis <ArrowRight size={14}/></Link></article></section>
    <section className="dashboard-grid lower-row"><article className="panel resources-panel"><div className="panel-header"><div><h2>Resource availability</h2><p>Fictional demo inventory · available of total</p></div><Link to="/resources" className="text-link">View resources <ArrowUpRight size={14}/></Link></div><div className="resource-list">{displayedResources.map((resource)=><div className="resource-row" key={resource.id}><div className={`resource-type-icon resource-${resource.icon}`}><ResourceIcon icon={resource.icon}/></div><div className="resource-info"><div><b>{resource.name}</b><span>{resource.available.toLocaleString()} <i>/</i> {resource.total.toLocaleString()} {resource.unit}</span></div><div className="resource-meter"><span style={{width:`${Math.round(resource.available/resource.total*100)}%`}} /></div></div><b className="resource-percent">{Math.round(resource.available/resource.total*100)}%</b></div>)}</div><div className="resource-footer"><span><i className="green-status-dot"/> {apiData?'Local API demo inventory':'Static demo inventory'}</span><ArrowUpRight size={14}/></div></article>
      <article className="panel alerts-panel"><div className="panel-header"><div><h2>Recent demo alerts</h2><p>Fictional sample updates</p></div><Link to="/alerts" className="text-link">All alerts <ArrowUpRight size={14}/></Link></div><div className="alert-list">{displayedAlerts.map(a=><div className="alert-item" key={a.id}><div className={`alert-symbol ${a.level}`}>{a.level==='critical'?<AlertTriangle size={15}/>:a.level==='warning'?<Package size={15}/>:<Bell size={15}/>}</div><div className="alert-copy"><b>{a.title}</b><span>{a.detail}</span><small><Clock3 size={11}/>{a.time}</small></div>{a.unread&&<span className={`alert-unread ${a.level}`} aria-label="Unread" />}</div>)}</div></article></section>
        <section className="panel recommendations-panel"><div className="panel-header"><div className="recommendation-heading"><div className="recommendation-spark"><Sparkles size={17}/></div><div><h2>Sample recommendation patterns</h2><p>Illustrative allocations · run optimization for a calculated proposal</p></div></div><Link to="/optimization" className="text-link">Open optimization <ArrowUpRight size={14}/></Link></div><div className="recommendation-list">{recommendations.map((recommendation)=>{const area=getAreaForRecommendation(recommendation.areaId);if(!area)return null;return <div className="recommendation-row" key={recommendation.areaId}><div className="rec-priority"><span className={`status-dot ${area.priority.toLowerCase()}-dot`}/><b>{area.priority}</b><small>Sample · {area.score}</small></div><div className="rec-content"><div className="rec-title"><strong>{area.name}</strong><span className="rec-chip">ILLUSTRATIVE ONLY</span></div><p>{recommendation.explanation}</p><div className="rec-allocation"><Boxes size={13}/>{formatRecommendationAllocation(recommendation.allocation)}</div></div><div className="rec-actions"><Link to="/optimization" className="button button-outline">Run optimization <ArrowRight size={13}/></Link></div></div>})}</div><div className="panel-disclaimer"><Shield size={13}/> Dashboard patterns are fictional examples. Optimization runs create persisted recommendations that require officer review. Nothing dispatches automatically.</div></section>
    <div className="bottom-note"><span><Activity size={13}/> Operational overview</span><span>Last refreshed {timeString} · Demo environment</span></div>
  </>
}

function ResourceIcon({icon}:{icon:typeof resources[number]['icon']}) {
  const icons = {
    ambulance: Ambulance,
    teams: LifeBuoy,
    medical: HeartPulse,
    food: Package,
    water: Waves,
    shelter: TentTree,
    transport: Truck,
  }
  const Icon = icons[icon]
  return <Icon size={16}/>
}

function AreaMarker({area}:{area:typeof areas[number]}) {
  const level = priorityLevels.find((item) => item.name === area.priority)
  const color = level?.color ?? '#a1adb4'
  return <Circle center={[area.lat,area.lng]} radius={level?.radiusMeters ?? 450} pathOptions={{color,fillColor:color,fillOpacity:.13,weight:1.4}}><Popup><div className="map-popup"><b>{area.name}</b><span className={`popup-priority ${area.priority.toLowerCase()}`}>{area.priority} sample class · score {area.score}</span><span>{area.population.toLocaleString()} people in sample data</span><span>{area.requests} grouped sample requests</span><span className="popup-coord">ILLUSTRATIVE DEMO AREA · {area.id}</span></div></Popup></Circle>
}

function OperationalMap({compact=false}:{compact?:boolean}) {
  const [filter,setFilter]=useState<Priority|'All'>('All')
  const [query,setQuery]=useState('')
  const [selectedArea,setSelectedArea]=useState<typeof areas[number]|undefined>()
  const shown=useMemo(()=>areas.filter((area)=>(filter==='All'||area.priority===filter)&&area.name.toLowerCase().includes(query.trim().toLowerCase())),[filter,query])
  const center = useMemo<[number,number]>(()=>[
    areas.reduce((total,area)=>total+area.lat,0)/areas.length,
    areas.reduce((total,area)=>total+area.lng,0)/areas.length,
  ],[])
  const metrics=getDashboardMetrics()
  return <div className={`map-frame ${compact?'map-compact':''}`} aria-label="Map with illustrative demo locations"><MapContainer center={center} zoom={11} scrollWheelZoom={false} zoomControl={!compact} className="leaflet-map"><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"/><MapFitBounds areas={shown} selectedArea={selectedArea}/>{shown.map(area=><AreaMarker key={area.id} area={area}/>)}{resourceCenters.map((resourceCenter)=><CircleMarker key={resourceCenter.id} center={[resourceCenter.lat,resourceCenter.lng]} radius={6} pathOptions={{color:'#a9d1f3',fillColor:'#579bd1',fillOpacity:.95,weight:2}}><Popup><div className="map-popup"><b>{resourceCenter.name}</b><span className="popup-coord">ILLUSTRATIVE RESOURCE CENTER</span></div></Popup></CircleMarker>)}</MapContainer><div className="map-label map-label-north" aria-hidden="true">N</div><div className="map-toolbar"><label className="map-search"><Search size={14}/><input aria-label="Search map areas" placeholder="Search area…" value={query} onChange={event=>{setQuery(event.target.value);setSelectedArea(undefined)}}/></label></div><div className="map-legend" aria-label="Filter areas by sample priority"><div className="legend-title">SAMPLE PRIORITY · FILTER</div>{priorityLevels.map(({name,color})=><button type="button" className={`legend-item ${filter===name?'legend-active':''}`} onClick={()=>{setFilter(filter===name?'All':name);setSelectedArea(undefined)}} key={name} aria-pressed={filter===name}><i style={{background:color}}/>{name}</button>)}{(filter!=='All'||query)&&<button type="button" onClick={()=>{setFilter('All');setQuery('');setSelectedArea(undefined)}} className="legend-clear">Clear filters</button>}</div><div className="map-attribution-note">Illustrative demo locations</div>{!compact&&<div className="map-side-panel"><div className="map-side-head"><div><span className="eyebrow">AFFECTED AREAS</span><h3>{shown.length} of {metrics.areaCount} demo areas</h3></div><button type="button" className="icon-button" onClick={()=>{setFilter('All');setQuery('');setSelectedArea(undefined)}} aria-label="Clear map filters"><X size={15}/></button></div><div className="map-area-list">{shown.length===0?<div className="map-empty-state" role="status">No demo areas match these filters.</div>:shown.map(area=><button type="button" className="map-area-item" key={area.id} aria-pressed={selectedArea?.id===area.id} onClick={()=>setSelectedArea(area)} aria-label={`${area.name}, ${area.priority} sample priority, score ${area.score}`}><span className={`status-dot ${area.priority.toLowerCase()}-dot`}/><span className="map-area-copy"><b>{area.name}</b><small>{area.population.toLocaleString()} demo population · {area.requests} grouped requests</small></span><span>{area.score}</span></button>)}</div><div className="map-centers-label">{metrics.resourceCenterCount} illustrative resource centers · blue markers</div></div>}</div>
}

function MapFitBounds({areas:items,selectedArea}:{areas:typeof areas;selectedArea?:typeof areas[number]}) { const map=useMap(); useEffect(()=>{if(selectedArea){map.flyTo([selectedArea.lat,selectedArea.lng],13,{duration:.4});return}if(items.length>0)map.fitBounds(L.latLngBounds(items.map(a=>[a.lat,a.lng])),{padding:[25,25],maxZoom:11})},[items,map,selectedArea]); return null }

function SectionPage({title}:{title:string}) {
  const metrics=getDashboardMetrics()
  return <>
    <div className="page-heading"><div><div className="eyebrow">{demoIncident.label}</div><h1>{title}</h1><p>Browse fictional sample areas and illustrative resource centers. No live incident is represented.</p></div><span className="incident-status"><i className="live-dot"/> {demoIncident.state}</span></div>
    <><div className="map-page-toolbar"><div><b>{metrics.areaCount}</b> illustrative demo areas <span>·</span> <b>{metrics.resourceCenterCount}</b> illustrative resource centers</div><div className="map-toolbar-caption">Filter by sample priority or search an area</div></div><OperationalMap /></>
  </>
}

export default App
