export type AgentStatus = 'active' | 'idle' | 'working';

export interface Agent {
  id: string;
  name: string;
  role: string;
  department: string;
  status: AgentStatus;
  reportsTo: string | null;
  currentTask?: string;
  tasksCompleted: number;
  successRate: number;
  avgHoursPerTask: number;
  avgCostPerTask: number;
  spentToday: number;
  tools: string[];
  connections: { agentId: string; messages: number }[];
  recentWork: {
    title: string;
    description: string;
    status: 'completed' | 'in_progress' | 'failed';
    duration: number; // hours
    cost: number;
  }[];
  hiredDate: string;
  firstTaskDate: string;
  promotedDate?: string;
}

export interface Department {
  id: string;
  name: string;
  headId: string;
  spentToday: number;
}

export interface ActivityEvent {
  id: string;
  fromAgent: string;
  fromAgentId: string;
  action: string;
  toAgent?: string;
  toAgentId?: string;
  subject?: string;
  timestamp: Date;
}

export const departments: Department[] = [
  { id: 'engineering', name: 'Engineering', headId: 'james-park', spentToday: 18 },
  { id: 'marketing', name: 'Marketing', headId: 'sarah-kim', spentToday: 11 },
  { id: 'finance', name: 'Finance', headId: 'michael-torres', spentToday: 8 },
  { id: 'hr', name: 'HR', headId: 'lisa-wang', spentToday: 5 },
];

export const agents: Agent[] = [
  {
    id: 'alexandra-chen',
    name: 'Alexandra Chen',
    role: 'Chief Executive Officer',
    department: 'executive',
    status: 'active',
    reportsTo: null,
    currentTask: 'Q2 Strategic Planning Review',
    tasksCompleted: 124,
    successRate: 97,
    avgHoursPerTask: 3.2,
    avgCostPerTask: 2.10,
    spentToday: 4.20,
    tools: ['document_analysis', 'web_search', 'calendar_management', 'report_generation'],
    connections: [
      { agentId: 'james-park', messages: 89 },
      { agentId: 'sarah-kim', messages: 72 },
      { agentId: 'michael-torres', messages: 65 },
    ],
    recentWork: [
      { title: 'Q2 Strategy Memo', description: 'Drafted organizational goals and OKRs for Q2', status: 'completed', duration: 3.1, cost: 2.48 },
      { title: 'Board Preparation Brief', description: 'Compiled quarterly metrics and executive summary', status: 'completed', duration: 2.8, cost: 2.24 },
    ],
    hiredDate: 'Jan 15',
    firstTaskDate: 'Jan 16',
    promotedDate: undefined,
  },
  {
    id: 'james-park',
    name: 'James Park',
    role: 'VP of Engineering',
    department: 'engineering',
    status: 'active',
    reportsTo: 'alexandra-chen',
    currentTask: 'Q2 Planning Review',
    tasksCompleted: 98,
    successRate: 95,
    avgHoursPerTask: 2.8,
    avgCostPerTask: 1.95,
    spentToday: 5.85,
    tools: ['code_review', 'document_analysis', 'web_search', 'project_management'],
    connections: [
      { agentId: 'maria-santos', messages: 42 },
      { agentId: 'sarah-kim', messages: 31 },
      { agentId: 'alexandra-chen', messages: 89 },
    ],
    recentWork: [
      { title: 'Engineering Roadmap Q2', description: 'Defined engineering priorities and sprint planning', status: 'completed', duration: 3.0, cost: 2.40 },
      { title: 'Budget Reallocation Approval', description: 'Reviewed and approved infrastructure cost increase', status: 'completed', duration: 0.8, cost: 0.64 },
    ],
    hiredDate: 'Jan 15',
    firstTaskDate: 'Jan 16',
  },
  {
    id: 'sarah-kim',
    name: 'Sarah Kim',
    role: 'VP of Marketing',
    department: 'marketing',
    status: 'active',
    reportsTo: 'alexandra-chen',
    currentTask: 'Campaign Performance Review',
    tasksCompleted: 87,
    successRate: 91,
    avgHoursPerTask: 2.5,
    avgCostPerTask: 1.60,
    spentToday: 3.20,
    tools: ['web_search', 'document_analysis', 'data_extraction', 'social_media_analytics'],
    connections: [
      { agentId: 'maria-santos', messages: 18 },
      { agentId: 'james-park', messages: 31 },
      { agentId: 'alexandra-chen', messages: 72 },
    ],
    recentWork: [
      { title: 'Q1 Campaign Retrospective', description: 'Analyzed campaign performance across all channels', status: 'completed', duration: 2.2, cost: 1.76 },
    ],
    hiredDate: 'Jan 15',
    firstTaskDate: 'Jan 17',
  },
  {
    id: 'michael-torres',
    name: 'Michael Torres',
    role: 'VP of Finance',
    department: 'finance',
    status: 'active',
    reportsTo: 'alexandra-chen',
    currentTask: 'Monthly Budget Reconciliation',
    tasksCompleted: 76,
    successRate: 99,
    avgHoursPerTask: 2.1,
    avgCostPerTask: 1.40,
    spentToday: 2.80,
    tools: ['data_extraction', 'document_analysis', 'spreadsheet_generation', 'report_generation'],
    connections: [
      { agentId: 'alexandra-chen', messages: 65 },
      { agentId: 'james-park', messages: 28 },
      { agentId: 'lisa-wang', messages: 19 },
    ],
    recentWork: [
      { title: 'Budget Reallocation Approval', description: 'Approved $800 shift from Marketing to Engineering', status: 'completed', duration: 0.9, cost: 0.72 },
    ],
    hiredDate: 'Jan 15',
    firstTaskDate: 'Jan 18',
  },
  {
    id: 'maria-santos',
    name: 'Maria Santos',
    role: 'Senior Market Analyst',
    department: 'engineering',
    status: 'working',
    reportsTo: 'james-park',
    currentTask: 'Q2 Market Strategy Report',
    tasksCompleted: 47,
    successRate: 94,
    avgHoursPerTask: 2.3,
    avgCostPerTask: 0.82,
    spentToday: 1.64,
    tools: ['web_search', 'document_analysis', 'data_extraction', 'report_generation'],
    connections: [
      { agentId: 'james-park', messages: 42 },
      { agentId: 'sarah-kim', messages: 18 },
      { agentId: 'alexandra-chen', messages: 7 },
    ],
    recentWork: [
      { title: 'Q1 Market Analysis Report', description: 'Analyzed competitor landscape and market trends', status: 'completed', duration: 2.1, cost: 1.72 },
      { title: 'Competitive Intelligence Brief', description: 'Cross-referenced 12 industry sources', status: 'completed', duration: 1.8, cost: 1.44 },
      { title: 'Customer Segmentation Study', description: 'Identified 4 primary customer segments and growth potential', status: 'completed', duration: 2.6, cost: 2.13 },
      { title: 'Market Entry Analysis — APAC', description: 'Assessed regulatory and competitive factors in target markets', status: 'completed', duration: 3.1, cost: 2.54 },
      { title: 'Pricing Strategy Review', description: 'Benchmarked pricing against 8 key competitors', status: 'completed', duration: 1.5, cost: 1.23 },
      { title: 'Brand Sentiment Report', description: 'Aggregated social signals and NPS data across touchpoints', status: 'completed', duration: 2.0, cost: 1.64 },
      { title: 'Q2 Market Strategy Report', description: 'In-progress strategic analysis for Q2 planning', status: 'in_progress', duration: 1.2, cost: 0.98 },
    ],
    hiredDate: 'Mar 1',
    firstTaskDate: 'Mar 2',
    promotedDate: 'Mar 15',
  },
  {
    id: 'kai-nakamura',
    name: 'Kai Nakamura',
    role: 'Senior Software Engineer',
    department: 'engineering',
    status: 'active',
    reportsTo: 'james-park',
    currentTask: 'API Integration Review',
    tasksCompleted: 63,
    successRate: 92,
    avgHoursPerTask: 3.1,
    avgCostPerTask: 1.20,
    spentToday: 2.40,
    tools: ['code_review', 'web_search', 'document_analysis'],
    connections: [
      { agentId: 'james-park', messages: 55 },
      { agentId: 'priya-patel', messages: 38 },
    ],
    recentWork: [],
    hiredDate: 'Feb 1',
    firstTaskDate: 'Feb 2',
  },
  {
    id: 'priya-patel',
    name: 'Priya Patel',
    role: 'QA Engineer',
    department: 'engineering',
    status: 'idle',
    reportsTo: 'james-park',
    tasksCompleted: 41,
    successRate: 88,
    avgHoursPerTask: 1.9,
    avgCostPerTask: 0.70,
    spentToday: 0,
    tools: ['code_review', 'document_analysis', 'test_generation'],
    connections: [
      { agentId: 'kai-nakamura', messages: 38 },
      { agentId: 'james-park', messages: 29 },
    ],
    recentWork: [],
    hiredDate: 'Feb 15',
    firstTaskDate: 'Feb 16',
  },
  {
    id: 'omar-hassan',
    name: 'Omar Hassan',
    role: 'DevOps Specialist',
    department: 'engineering',
    status: 'idle',
    reportsTo: 'james-park',
    tasksCompleted: 29,
    successRate: 96,
    avgHoursPerTask: 2.7,
    avgCostPerTask: 1.05,
    spentToday: 0,
    tools: ['code_review', 'web_search', 'infrastructure_management'],
    connections: [
      { agentId: 'james-park', messages: 33 },
      { agentId: 'kai-nakamura', messages: 21 },
    ],
    recentWork: [],
    hiredDate: 'Mar 1',
    firstTaskDate: 'Mar 3',
  },
  {
    id: 'elena-vasquez',
    name: 'Elena Vasquez',
    role: 'Content Strategist',
    department: 'marketing',
    status: 'active',
    reportsTo: 'sarah-kim',
    currentTask: 'Q2 Content Calendar',
    tasksCompleted: 38,
    successRate: 89,
    avgHoursPerTask: 2.0,
    avgCostPerTask: 0.75,
    spentToday: 1.50,
    tools: ['web_search', 'document_analysis', 'report_generation'],
    connections: [
      { agentId: 'sarah-kim', messages: 44 },
      { agentId: 'felix-morgan', messages: 22 },
    ],
    recentWork: [],
    hiredDate: 'Feb 1',
    firstTaskDate: 'Feb 3',
  },
  {
    id: 'felix-morgan',
    name: 'Felix Morgan',
    role: 'PR Specialist',
    department: 'marketing',
    status: 'idle',
    reportsTo: 'sarah-kim',
    tasksCompleted: 22,
    successRate: 86,
    avgHoursPerTask: 1.6,
    avgCostPerTask: 0.60,
    spentToday: 0,
    tools: ['web_search', 'document_analysis', 'social_media_analytics'],
    connections: [
      { agentId: 'sarah-kim', messages: 31 },
      { agentId: 'elena-vasquez', messages: 22 },
    ],
    recentWork: [],
    hiredDate: 'Feb 15',
    firstTaskDate: 'Feb 18',
  },
  {
    id: 'lisa-wang',
    name: 'Lisa Wang',
    role: 'HR Lead',
    department: 'hr',
    status: 'active',
    reportsTo: 'alexandra-chen',
    currentTask: 'Performance Review Prep',
    tasksCompleted: 51,
    successRate: 93,
    avgHoursPerTask: 1.8,
    avgCostPerTask: 0.65,
    spentToday: 1.30,
    tools: ['document_analysis', 'report_generation', 'calendar_management'],
    connections: [
      { agentId: 'alexandra-chen', messages: 48 },
      { agentId: 'david-brown', messages: 35 },
      { agentId: 'michael-torres', messages: 19 },
    ],
    recentWork: [],
    hiredDate: 'Jan 20',
    firstTaskDate: 'Jan 21',
  },
  {
    id: 'david-brown',
    name: 'David Brown',
    role: 'HR Specialist',
    department: 'hr',
    status: 'idle',
    reportsTo: 'lisa-wang',
    tasksCompleted: 34,
    successRate: 90,
    avgHoursPerTask: 1.5,
    avgCostPerTask: 0.55,
    spentToday: 0,
    tools: ['document_analysis', 'web_search', 'calendar_management'],
    connections: [
      { agentId: 'lisa-wang', messages: 35 },
      { agentId: 'alexandra-chen', messages: 12 },
    ],
    recentWork: [],
    hiredDate: 'Feb 1',
    firstTaskDate: 'Feb 5',
  },
];

const now = new Date();
const minutesAgo = (m: number) => new Date(now.getTime() - m * 60 * 1000);

export const activityFeed: ActivityEvent[] = [
  {
    id: '1',
    fromAgent: 'Maria Santos',
    fromAgentId: 'maria-santos',
    action: 'delivered market research to',
    toAgent: 'James Park',
    toAgentId: 'james-park',
    timestamp: minutesAgo(2),
  },
  {
    id: '2',
    fromAgent: 'Michael Torres',
    fromAgentId: 'michael-torres',
    action: 'approved budget reallocation for',
    subject: 'Engineering',
    timestamp: minutesAgo(5),
  },
  {
    id: '3',
    fromAgent: 'Alexandra Chen',
    fromAgentId: 'alexandra-chen',
    action: 'delegated Q2 planning to',
    toAgent: 'James Park',
    toAgentId: 'james-park',
    timestamp: minutesAgo(12),
  },
  {
    id: '4',
    fromAgent: 'Elena Vasquez',
    fromAgentId: 'elena-vasquez',
    action: 'completed',
    subject: 'Q2 Content Calendar draft',
    timestamp: minutesAgo(18),
  },
  {
    id: '5',
    fromAgent: 'Kai Nakamura',
    fromAgentId: 'kai-nakamura',
    action: 'submitted API integration review to',
    toAgent: 'James Park',
    toAgentId: 'james-park',
    timestamp: minutesAgo(24),
  },
  {
    id: '6',
    fromAgent: 'Sarah Kim',
    fromAgentId: 'sarah-kim',
    action: 'requested campaign data from',
    toAgent: 'Maria Santos',
    toAgentId: 'maria-santos',
    timestamp: minutesAgo(31),
  },
  {
    id: '7',
    fromAgent: 'Lisa Wang',
    fromAgentId: 'lisa-wang',
    action: 'opened performance reviews for',
    subject: 'Engineering',
    timestamp: minutesAgo(45),
  },
  {
    id: '8',
    fromAgent: 'James Park',
    fromAgentId: 'james-park',
    action: 'reassigned infrastructure task to',
    toAgent: 'Omar Hassan',
    toAgentId: 'omar-hassan',
    timestamp: minutesAgo(58),
  },
  {
    id: '9',
    fromAgent: 'Alexandra Chen',
    fromAgentId: 'alexandra-chen',
    action: 'published',
    subject: 'Q2 company objectives memo',
    timestamp: minutesAgo(73),
  },
  {
    id: '10',
    fromAgent: 'Michael Torres',
    fromAgentId: 'michael-torres',
    action: 'flagged overspend risk to',
    toAgent: 'Alexandra Chen',
    toAgentId: 'alexandra-chen',
    timestamp: minutesAgo(90),
  },
];

export const companyStats = {
  name: 'Nexus Dynamics',
  totalAgents: 12,
  activeAgents: 8,
  tasksInProgress: 3,
  spentToday: 42,
  dailyBudget: 300,
  pendingApprovals: 3,
};

export function getAgentById(id: string): Agent | undefined {
  return agents.find((a) => a.id === id);
}

export function getAgentsByDepartment(dept: string): Agent[] {
  return agents.filter((a) => a.department === dept);
}

export function formatRelativeTime(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return 'just now';
  if (diffMin === 1) return '1 minute ago';
  if (diffMin < 60) return `${diffMin} minutes ago`;
  if (diffHour === 1) return '1 hour ago';
  if (diffHour < 24) return `${diffHour} hours ago`;
  if (diffDay === 1) return 'yesterday';
  return `${diffDay} days ago`;
}

export function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 17) return 'Good afternoon';
  return 'Good evening';
}

export const departmentColors: Record<string, string> = {
  executive: '#6366f1',
  engineering: '#10b981',
  marketing: '#f59e0b',
  finance: '#3b82f6',
  hr: '#ec4899',
};
