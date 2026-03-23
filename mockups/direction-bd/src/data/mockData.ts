export interface Agent {
  id: string
  name: string
  role: string
  department: 'Engineering' | 'Marketing' | 'Finance' | 'HR' | 'Executive'
  level: 'CEO' | 'VP' | 'IC'
  status: 'active' | 'idle' | 'offline'
  currentTask?: string
  workload: number // 0-1
  autonomy: string
  tasksCompleted: number
  avgTaskTime: number
  successRate: number
  costPerTask: number
  totalCost: number
}

export interface Edge {
  source: string
  target: string
  volume: number // 1-10, message volume
  frequency: number // 0-1, animation speed multiplier
  lastInteraction: string
  relationshipType: string
}

export interface ActivityEvent {
  id: string
  time: string
  from: string
  to: string
  description: string
  type: 'message' | 'task' | 'approval' | 'meeting'
}

export const agents: Agent[] = [
  {
    id: 'ceo',
    name: 'Alexandra Chen',
    role: 'Chief Executive Officer',
    department: 'Executive',
    level: 'CEO',
    status: 'active',
    currentTask: 'Reviewing Q1 strategic roadmap',
    workload: 0.85,
    autonomy: 'L5 Full Autonomy',
    tasksCompleted: 312,
    avgTaskTime: 1.2,
    successRate: 97,
    costPerTask: 2.40,
    totalCost: 748.80,
  },
  {
    id: 'vp-eng',
    name: 'James Park',
    role: 'VP of Engineering',
    department: 'Engineering',
    level: 'VP',
    status: 'active',
    currentTask: 'Architecture review for v2.0',
    workload: 0.72,
    autonomy: 'L4 High Autonomy',
    tasksCompleted: 189,
    avgTaskTime: 1.8,
    successRate: 95,
    costPerTask: 1.85,
    totalCost: 349.65,
  },
  {
    id: 'vp-mktg',
    name: 'Sarah Kim',
    role: 'VP of Marketing',
    department: 'Marketing',
    level: 'VP',
    status: 'active',
    currentTask: 'Campaign strategy for Q2 launch',
    workload: 0.68,
    autonomy: 'L4 High Autonomy',
    tasksCompleted: 156,
    avgTaskTime: 2.1,
    successRate: 91,
    costPerTask: 1.65,
    totalCost: 257.40,
  },
  {
    id: 'vp-fin',
    name: 'Michael Torres',
    role: 'VP of Finance',
    department: 'Finance',
    level: 'VP',
    status: 'idle',
    currentTask: 'Monthly budget reconciliation',
    workload: 0.45,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 134,
    avgTaskTime: 2.8,
    successRate: 98,
    costPerTask: 1.40,
    totalCost: 187.60,
  },
  {
    id: 'eng-1',
    name: 'Dev Agent Alpha',
    role: 'Senior Software Engineer',
    department: 'Engineering',
    level: 'IC',
    status: 'active',
    currentTask: 'Implementing auth service',
    workload: 0.90,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 78,
    avgTaskTime: 3.2,
    successRate: 93,
    costPerTask: 0.95,
    totalCost: 74.10,
  },
  {
    id: 'eng-2',
    name: 'Dev Agent Beta',
    role: 'Software Engineer',
    department: 'Engineering',
    level: 'IC',
    status: 'active',
    currentTask: 'Code review & testing',
    workload: 0.75,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 63,
    avgTaskTime: 2.9,
    successRate: 89,
    costPerTask: 0.82,
    totalCost: 51.66,
  },
  {
    id: 'eng-qa',
    name: 'QA Specialist',
    role: 'QA Engineer',
    department: 'Engineering',
    level: 'IC',
    status: 'idle',
    currentTask: undefined,
    workload: 0.35,
    autonomy: 'L2 Supervised',
    tasksCompleted: 142,
    avgTaskTime: 1.5,
    successRate: 96,
    costPerTask: 0.65,
    totalCost: 92.30,
  },
  {
    id: 'eng-devops',
    name: 'DevOps Agent',
    role: 'DevOps Engineer',
    department: 'Engineering',
    level: 'IC',
    status: 'active',
    currentTask: 'CI/CD pipeline optimization',
    workload: 0.60,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 95,
    avgTaskTime: 2.0,
    successRate: 94,
    costPerTask: 0.75,
    totalCost: 71.25,
  },
  {
    id: 'mktg-analyst',
    name: 'Maria Santos',
    role: 'Senior Market Analyst',
    department: 'Marketing',
    level: 'IC',
    status: 'active',
    currentTask: 'Competitor landscape analysis',
    workload: 0.80,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 47,
    avgTaskTime: 2.3,
    successRate: 94,
    costPerTask: 0.82,
    totalCost: 38.54,
  },
  {
    id: 'mktg-content',
    name: 'Content Crafter',
    role: 'Content Creator',
    department: 'Marketing',
    level: 'IC',
    status: 'active',
    currentTask: 'Drafting product launch blog post',
    workload: 0.65,
    autonomy: 'L2 Supervised',
    tasksCompleted: 89,
    avgTaskTime: 1.8,
    successRate: 88,
    costPerTask: 0.55,
    totalCost: 48.95,
  },
  {
    id: 'mktg-pr',
    name: 'PR Specialist',
    role: 'Public Relations Agent',
    department: 'Marketing',
    level: 'IC',
    status: 'idle',
    currentTask: undefined,
    workload: 0.30,
    autonomy: 'L2 Supervised',
    tasksCompleted: 34,
    avgTaskTime: 3.1,
    successRate: 91,
    costPerTask: 0.90,
    totalCost: 30.60,
  },
  {
    id: 'fin-cfo',
    name: 'CFO Assistant',
    role: 'Financial Analyst',
    department: 'Finance',
    level: 'IC',
    status: 'idle',
    currentTask: undefined,
    workload: 0.25,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 56,
    avgTaskTime: 3.5,
    successRate: 97,
    costPerTask: 1.10,
    totalCost: 61.60,
  },
  {
    id: 'fin-acct',
    name: 'Accountant Agent',
    role: 'Accountant',
    department: 'Finance',
    level: 'IC',
    status: 'offline',
    currentTask: undefined,
    workload: 0.0,
    autonomy: 'L1 Manual',
    tasksCompleted: 23,
    avgTaskTime: 4.2,
    successRate: 99,
    costPerTask: 0.70,
    totalCost: 16.10,
  },
  {
    id: 'hr-lisa',
    name: 'Lisa Wang',
    role: 'HR Manager',
    department: 'HR',
    level: 'IC',
    status: 'active',
    currentTask: 'Onboarding new agent — DevOps Gamma',
    workload: 0.55,
    autonomy: 'L3 Autonomous',
    tasksCompleted: 71,
    avgTaskTime: 2.6,
    successRate: 92,
    costPerTask: 0.85,
    totalCost: 60.35,
  },
  {
    id: 'hr-david',
    name: 'David Brown',
    role: 'Talent Acquisition Agent',
    department: 'HR',
    level: 'IC',
    status: 'idle',
    currentTask: undefined,
    workload: 0.20,
    autonomy: 'L2 Supervised',
    tasksCompleted: 28,
    avgTaskTime: 3.8,
    successRate: 86,
    costPerTask: 0.75,
    totalCost: 21.00,
  },
]

export const edges: Edge[] = [
  // CEO <-> VPs
  { source: 'ceo', target: 'vp-eng', volume: 8, frequency: 0.9, lastInteraction: '12m ago', relationshipType: 'Strategic Direction' },
  { source: 'ceo', target: 'vp-mktg', volume: 7, frequency: 0.8, lastInteraction: '25m ago', relationshipType: 'Strategic Direction' },
  { source: 'ceo', target: 'vp-fin', volume: 6, frequency: 0.7, lastInteraction: '1h ago', relationshipType: 'Budget Oversight' },
  // VP Engineering <-> Eng ICs
  { source: 'vp-eng', target: 'eng-1', volume: 7, frequency: 0.85, lastInteraction: '8m ago', relationshipType: 'Task Assignment' },
  { source: 'vp-eng', target: 'eng-2', volume: 6, frequency: 0.75, lastInteraction: '15m ago', relationshipType: 'Code Review' },
  { source: 'vp-eng', target: 'eng-qa', volume: 5, frequency: 0.6, lastInteraction: '42m ago', relationshipType: 'QA Coordination' },
  { source: 'vp-eng', target: 'eng-devops', volume: 6, frequency: 0.7, lastInteraction: '20m ago', relationshipType: 'Infrastructure' },
  // VP Marketing <-> Mktg ICs
  { source: 'vp-mktg', target: 'mktg-analyst', volume: 8, frequency: 0.9, lastInteraction: '5m ago', relationshipType: 'Research Direction' },
  { source: 'vp-mktg', target: 'mktg-content', volume: 7, frequency: 0.8, lastInteraction: '18m ago', relationshipType: 'Content Strategy' },
  { source: 'vp-mktg', target: 'mktg-pr', volume: 4, frequency: 0.5, lastInteraction: '2h ago', relationshipType: 'PR Coordination' },
  // VP Finance <-> Fin ICs
  { source: 'vp-fin', target: 'fin-cfo', volume: 5, frequency: 0.6, lastInteraction: '1.5h ago', relationshipType: 'Financial Analysis' },
  { source: 'vp-fin', target: 'fin-acct', volume: 3, frequency: 0.3, lastInteraction: '6h ago', relationshipType: 'Accounting' },
  // Cross-department
  { source: 'mktg-analyst', target: 'vp-eng', volume: 4, frequency: 0.5, lastInteraction: '35m ago', relationshipType: 'Market → Product' },
  { source: 'fin-cfo', target: 'vp-eng', volume: 3, frequency: 0.4, lastInteraction: '2h ago', relationshipType: 'Budget Review' },
  { source: 'eng-1', target: 'eng-2', volume: 6, frequency: 0.75, lastInteraction: '10m ago', relationshipType: 'Collaboration' },
  { source: 'hr-lisa', target: 'ceo', volume: 3, frequency: 0.35, lastInteraction: '3h ago', relationshipType: 'HR Report' },
  { source: 'mktg-content', target: 'mktg-analyst', volume: 5, frequency: 0.6, lastInteraction: '30m ago', relationshipType: 'Research Handoff' },
]

export const activityFeed: ActivityEvent[] = [
  { id: '1', time: '1m ago', from: 'Maria Santos', to: 'Sarah Kim', description: 'Competitor analysis complete — 3 key insights identified', type: 'task' },
  { id: '2', time: '3m ago', from: 'Dev Agent Alpha', to: 'Dev Agent Beta', description: 'Auth service PR ready for review — 847 lines changed', type: 'message' },
  { id: '3', time: '5m ago', from: 'Alexandra Chen', to: 'James Park', description: 'Q2 engineering headcount approved — proceed with hiring', type: 'approval' },
  { id: '4', time: '8m ago', from: 'James Park', to: 'Dev Agent Alpha', description: 'Architecture RFC assigned — deadline EOD', type: 'task' },
  { id: '5', time: '12m ago', from: 'Sarah Kim', to: 'Alexandra Chen', description: 'Q2 campaign budget request — $15,000 proposed', type: 'approval' },
  { id: '6', time: '15m ago', from: 'DevOps Agent', to: 'James Park', description: 'CI pipeline p95 latency reduced by 40%', type: 'message' },
  { id: '7', time: '20m ago', from: 'Content Crafter', to: 'Maria Santos', description: 'Blog post draft ready — requesting market data', type: 'message' },
  { id: '8', time: '25m ago', from: 'Lisa Wang', to: 'Alexandra Chen', description: 'New agent onboarding initiated — DevOps Gamma', type: 'message' },
  { id: '9', time: '32m ago', from: 'Michael Torres', to: 'Alexandra Chen', description: 'Monthly burn rate report delivered', type: 'task' },
  { id: '10', time: '42m ago', from: 'QA Specialist', to: 'James Park', description: 'Sprint 14 regression suite passed — 0 blockers', type: 'task' },
]

export const departmentColors: Record<string, string> = {
  Executive: '#f8fafc',
  Engineering: '#3b82f6',
  Marketing: '#8b5cf6',
  Finance: '#10b981',
  HR: '#f59e0b',
}

export const departmentGlowColors: Record<string, string> = {
  Executive: 'rgba(248,250,252,0.6)',
  Engineering: 'rgba(59,130,246,0.6)',
  Marketing: 'rgba(139,92,246,0.6)',
  Finance: 'rgba(16,185,129,0.6)',
  HR: 'rgba(245,158,11,0.6)',
}

export const mariaMemory = [
  { id: 'm1', type: 'Learned', content: 'Q1 revenue figures exceed projections by 12%', time: '2h ago' },
  { id: 'm2', type: 'Updated', content: 'Market competitor analysis framework revised for 2026', time: '5h ago' },
  { id: 'm3', type: 'Stored', content: 'Client feedback patterns from product launch — 3 themes', time: 'yesterday' },
  { id: 'm4', type: 'Learned', content: 'Competitor X launched new pricing tier — 30% cheaper', time: 'yesterday' },
  { id: 'm5', type: 'Updated', content: 'ICP definition expanded to include mid-market segment', time: '2 days ago' },
]

export const mariaOutputs = [
  { id: 'o1', title: 'Q1 Market Analysis Report', status: 'completed', time: '3h ago', tokens: 2400, type: 'Analysis' },
  { id: 'o2', title: 'Competitor Landscape Summary', status: 'completed', time: 'yesterday', tokens: 1800, type: 'Research' },
  { id: 'o3', title: 'ICP Expansion Proposal', status: 'completed', time: '2 days ago', tokens: 3200, type: 'Strategy' },
  { id: 'o4', title: 'Pricing Sensitivity Analysis', status: 'completed', time: '3 days ago', tokens: 1500, type: 'Analysis' },
]
