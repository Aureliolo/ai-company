import type {
  Agent,
  AgentStatus,
  TaskEntry,
  ActivityEntry,
  CareerEvent,
} from "@/data/types"
import { createRng, pick, randInt, randFloat, weightedPick } from "@/data/seed"

// ---------------------------------------------------------------------------
// Curated name pool (60 diverse names)
// ---------------------------------------------------------------------------

const NAMES = [
  "Alexandra Chen",
  "James Park",
  "Maria Santos",
  "Kai Nakamura",
  "Lena Fischer",
  "Alex Rivera",
  "Sam Okonkwo",
  "Priya Sharma",
  "Jordan Lee",
  "Lisa Wang",
  "David Brown",
  "Michael Torres",
  "Sarah Kim",
  "Emma Wright",
  "Noah Patel",
  "Yuki Tanaka",
  "Omar Hassan",
  "Aisha Patel",
  "Lucas Bergstrom",
  "Isabella Martinez",
  "Dmitri Volkov",
  "Fatima Al-Rashid",
  "Thomas Mueller",
  "Amara Obi",
  "Rajesh Kumar",
  "Sophie Laurent",
  "Marcus Johnson",
  "Hana Kimura",
  "Carlos Gutierrez",
  "Elena Popescu",
  "Wei Zhang",
  "Jasmine Okafor",
  "Henrik Larsen",
  "Valentina Rossi",
  "Kwame Asante",
  "Mei-Ling Wu",
  "Patrick O'Brien",
  "Nadia Petrova",
  "Tariq Ahmed",
  "Celine Dubois",
  "Andre Williams",
  "Yara Benali",
  "Gustaf Eriksson",
  "Chiara Romano",
  "Kofi Mensah",
  "Ingrid Svenson",
  "Diego Morales",
  "Rina Takahashi",
  "Amir Farahani",
  "Olga Novikova",
  "Benjamin Adler",
  "Fatou Diallo",
  "Jin-Ho Park",
  "Camille Leroy",
  "Dante Silva",
  "Astrid Johansson",
  "Rohan Mehta",
  "Leila Khoury",
  "Tobias Becker",
  "Zara Osman",
] as const

// ---------------------------------------------------------------------------
// Department definitions
// ---------------------------------------------------------------------------

interface RoleDef {
  role: string
  level: Agent["level"]
  shortPrefix: string
}

interface DepartmentDef {
  name: string
  roles: RoleDef[]
  tools: string[]
  taskNames: string[]
  taskTypes: TaskEntry["type"][]
}

const DEPARTMENTS: DepartmentDef[] = [
  {
    name: "Engineering",
    roles: [
      { role: "VP Engineering", level: "VP", shortPrefix: "VP-Eng" },
      { role: "Lead Developer", level: "Lead", shortPrefix: "Lead-Dev" },
      { role: "Senior Developer", level: "Senior", shortPrefix: "Sr-Dev" },
      { role: "Senior Developer", level: "Senior", shortPrefix: "Sr-Dev" },
      { role: "Senior Developer", level: "Senior", shortPrefix: "Sr-Dev" },
      { role: "Developer", level: "Mid", shortPrefix: "Dev" },
      { role: "Developer", level: "Mid", shortPrefix: "Dev" },
      { role: "Developer", level: "Mid", shortPrefix: "Dev" },
      { role: "Developer", level: "Mid", shortPrefix: "Dev" },
      { role: "Junior Developer", level: "Junior", shortPrefix: "Jr-Dev" },
      { role: "Junior Developer", level: "Junior", shortPrefix: "Jr-Dev" },
      { role: "QA Engineer", level: "Mid", shortPrefix: "QA" },
      { role: "QA Engineer", level: "Mid", shortPrefix: "QA" },
      { role: "DevOps Engineer", level: "Senior", shortPrefix: "DevOps" },
      {
        role: "Security Engineer",
        level: "Senior",
        shortPrefix: "SecEng",
      },
    ],
    tools: [
      "code_review",
      "test_runner",
      "deployment",
      "monitoring",
      "debug_tools",
      "documentation",
      "git_operations",
      "ci_cd",
    ],
    taskNames: [
      "API endpoint refactor",
      "Database migration v3",
      "Auth module rewrite",
      "Performance profiling sprint",
      "WebSocket reconnection fix",
      "Rate limiter implementation",
      "Unit test coverage push",
      "CI pipeline optimization",
      "Memory leak investigation",
      "GraphQL schema update",
      "Docker image slimming",
      "Dependency audit Q1",
      "Error boundary hardening",
      "Cache invalidation rework",
      "Logging pipeline overhaul",
      "SDK versioning strategy",
      "Load testing harness",
      "Config hot-reload support",
      "Telemetry data pipeline",
      "Security patch rollout",
    ],
    taskTypes: ["development", "review", "analysis", "operations"],
  },
  {
    name: "Marketing",
    roles: [
      { role: "VP Marketing", level: "VP", shortPrefix: "VP-Mkt" },
      {
        role: "Senior Market Analyst",
        level: "Senior",
        shortPrefix: "Sr-Analyst",
      },
      {
        role: "Content Creator",
        level: "Mid",
        shortPrefix: "Content",
      },
      {
        role: "Content Creator",
        level: "Mid",
        shortPrefix: "Content",
      },
      { role: "PR Specialist", level: "Mid", shortPrefix: "PR" },
      { role: "SEO Specialist", level: "Mid", shortPrefix: "SEO" },
      {
        role: "Growth Analyst",
        level: "Junior",
        shortPrefix: "Growth",
      },
    ],
    tools: [
      "web_search",
      "content_creation",
      "analytics",
      "social_media",
      "seo_tools",
      "email_campaigns",
      "report_generation",
    ],
    taskNames: [
      "Q2 Campaign Strategy",
      "Competitor Landscape Analysis",
      "Brand Voice Guidelines",
      "Social Media Calendar Q2",
      "Email Drip Sequence Design",
      "Landing Page A/B Test",
      "SEO Keyword Research Sprint",
      "Content Performance Report",
      "Press Release Draft",
      "Influencer Outreach Plan",
      "Product Launch Playbook",
      "Customer Testimonial Compilation",
      "Market Segmentation Study",
      "Newsletter Redesign",
      "Paid Ads ROI Analysis",
      "Blog Editorial Calendar",
      "Webinar Promotion Strategy",
    ],
    taskTypes: ["research", "analysis", "report", "outreach", "design"],
  },
  {
    name: "Finance",
    roles: [
      { role: "CFO", level: "C-Suite", shortPrefix: "CFO" },
      {
        role: "Senior Accountant",
        level: "Senior",
        shortPrefix: "Sr-Acct",
      },
      { role: "Accountant", level: "Mid", shortPrefix: "Acct" },
      { role: "Accountant", level: "Mid", shortPrefix: "Acct" },
      {
        role: "Financial Analyst",
        level: "Mid",
        shortPrefix: "Fin-Analyst",
      },
    ],
    tools: [
      "spreadsheet",
      "data_analysis",
      "report_generation",
      "budget_forecasting",
      "expense_tracking",
      "audit_tools",
    ],
    taskNames: [
      "Monthly P&L Reconciliation",
      "Budget Variance Report",
      "Vendor Payment Audit",
      "Cash Flow Forecast Q2",
      "Expense Policy Update",
      "Tax Provision Estimate",
      "Cost Center Reallocation",
      "Revenue Recognition Review",
      "Capital Expenditure Analysis",
      "Payroll Accuracy Audit",
      "Financial Dashboard Build",
      "Quarterly Board Report",
      "Procurement Savings Analysis",
      "Intercompany Transfer Reconciliation",
      "Depreciation Schedule Update",
    ],
    taskTypes: ["analysis", "report", "review", "operations"],
  },
  {
    name: "HR",
    roles: [
      { role: "VP People", level: "VP", shortPrefix: "VP-HR" },
      { role: "HR Manager", level: "Senior", shortPrefix: "HR-Mgr" },
      {
        role: "HR Coordinator",
        level: "Mid",
        shortPrefix: "HR-Coord",
      },
      { role: "Recruiter", level: "Mid", shortPrefix: "Recruiter" },
    ],
    tools: [
      "candidate_search",
      "scheduling",
      "document_analysis",
      "communication",
      "policy_tools",
      "training_management",
    ],
    taskNames: [
      "Onboarding Workflow Redesign",
      "Compensation Benchmark Study",
      "Employee Satisfaction Survey",
      "Performance Review Cycle Setup",
      "Policy Handbook Revision",
      "Diversity Metrics Dashboard",
      "Training Curriculum Plan",
      "Exit Interview Analysis",
      "Headcount Planning Q2",
      "Benefits Package Comparison",
      "Candidate Pipeline Review",
      "Culture Initiatives Proposal",
      "Compliance Training Rollout",
      "Retention Risk Assessment",
      "Job Description Standardization",
    ],
    taskTypes: ["research", "analysis", "report", "operations"],
  },
  {
    name: "Product",
    roles: [
      { role: "VP Product", level: "VP", shortPrefix: "VP-Prod" },
      {
        role: "Product Manager",
        level: "Senior",
        shortPrefix: "PM",
      },
      {
        role: "Product Manager",
        level: "Senior",
        shortPrefix: "PM",
      },
      {
        role: "UX Researcher",
        level: "Mid",
        shortPrefix: "UX",
      },
      {
        role: "Technical Writer",
        level: "Mid",
        shortPrefix: "TechWriter",
      },
    ],
    tools: [
      "user_research",
      "analytics",
      "prototyping",
      "documentation",
      "roadmap_tools",
      "survey_tools",
    ],
    taskNames: [
      "Feature Prioritization Framework",
      "User Journey Mapping",
      "Competitive Analysis Q1",
      "Roadmap Presentation Prep",
      "Usability Test Round 4",
      "PRD: Agent Autonomy Levels",
      "Metrics Definition Workshop",
      "Beta Feedback Synthesis",
      "Release Notes Drafting",
      "API Documentation Overhaul",
      "Persona Research Update",
      "Feature Flag Strategy",
      "Customer Interview Synthesis",
      "Sprint Retrospective Report",
      "Accessibility Audit Plan",
      "Onboarding Flow Prototype",
    ],
    taskTypes: ["research", "analysis", "design", "report"],
  },
  {
    name: "Sales",
    roles: [
      { role: "VP Sales", level: "VP", shortPrefix: "VP-Sales" },
      {
        role: "Senior Account Executive",
        level: "Senior",
        shortPrefix: "Sr-AE",
      },
      {
        role: "Senior Account Executive",
        level: "Senior",
        shortPrefix: "Sr-AE",
      },
      {
        role: "Account Executive",
        level: "Mid",
        shortPrefix: "AE",
      },
      {
        role: "Account Executive",
        level: "Mid",
        shortPrefix: "AE",
      },
      {
        role: "Sales Analyst",
        level: "Junior",
        shortPrefix: "Sales-Analyst",
      },
    ],
    tools: [
      "crm_tools",
      "email_outreach",
      "proposal_generator",
      "analytics",
      "meeting_scheduler",
      "presentation_tools",
    ],
    taskNames: [
      "Enterprise Pipeline Review",
      "Q2 Quota Planning",
      "Proposal: Acme Corp Deal",
      "CRM Data Cleanup Sprint",
      "Win/Loss Analysis Q1",
      "Sales Enablement Deck",
      "Territory Mapping Update",
      "Demo Script Refinement",
      "Contract Negotiation Prep",
      "Outbound Cadence Optimization",
      "Referral Program Launch",
      "Pricing Strategy Review",
      "Partner Channel Assessment",
      "Customer Expansion Playbook",
      "Sales Forecast Calibration",
      "Competitive Battlecard Update",
    ],
    taskTypes: ["outreach", "analysis", "report", "operations"],
  },
  {
    name: "Legal",
    roles: [
      {
        role: "General Counsel",
        level: "C-Suite",
        shortPrefix: "GC",
      },
      {
        role: "Corporate Attorney",
        level: "Senior",
        shortPrefix: "Attorney",
      },
      {
        role: "Compliance Analyst",
        level: "Mid",
        shortPrefix: "Compliance",
      },
    ],
    tools: [
      "document_analysis",
      "legal_research",
      "contract_tools",
      "compliance_scanner",
      "communication",
    ],
    taskNames: [
      "NDA Template Revision",
      "Data Privacy Compliance Audit",
      "IP Portfolio Review",
      "Vendor Contract Negotiation",
      "Regulatory Change Assessment",
      "Employee Agreement Updates",
      "Open Source License Audit",
      "GDPR Data Mapping",
      "Corporate Governance Review",
      "Liability Risk Assessment",
      "Trademark Filing Prep",
      "Compliance Training Materials",
      "Board Resolution Drafting",
      "Incident Response Legal Playbook",
      "Terms of Service Update",
    ],
    taskTypes: ["review", "analysis", "report", "research"],
  },
  {
    name: "Operations",
    roles: [
      { role: "VP Operations", level: "VP", shortPrefix: "VP-Ops" },
      {
        role: "Operations Manager",
        level: "Senior",
        shortPrefix: "Ops-Mgr",
      },
      {
        role: "Operations Analyst",
        level: "Mid",
        shortPrefix: "Ops-Analyst",
      },
      {
        role: "Operations Analyst",
        level: "Mid",
        shortPrefix: "Ops-Analyst",
      },
      {
        role: "Logistics Coordinator",
        level: "Junior",
        shortPrefix: "Logistics",
      },
    ],
    tools: [
      "process_automation",
      "monitoring",
      "logistics_tools",
      "vendor_management",
      "incident_response",
    ],
    taskNames: [
      "SLA Compliance Dashboard",
      "Vendor Performance Scorecard",
      "Incident Response Drill",
      "Process Automation Audit",
      "Capacity Planning Q2",
      "Cost Optimization Review",
      "Supply Chain Risk Analysis",
      "Workflow Bottleneck Study",
      "Service Catalog Update",
      "Disaster Recovery Test",
      "Office Space Optimization",
      "Tool Consolidation Assessment",
      "Runbook Documentation Sprint",
      "Change Management Framework",
      "Operational Metrics Review",
      "Infrastructure Cost Allocation",
    ],
    taskTypes: ["operations", "analysis", "report", "review"],
  },
]

// ---------------------------------------------------------------------------
// Helpers for generation
// ---------------------------------------------------------------------------

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
]

function formatDate(month: number, day: number, year: number): string {
  return `${MONTHS[month]} ${day}, ${year}`
}

function autonomyForLevel(level: Agent["level"]): string {
  switch (level) {
    case "C-Suite":
    case "VP":
      return "L4 Strategic"
    case "Lead":
    case "Senior":
      return "L3 Autonomous"
    case "Mid":
      return "L2 Guided"
    case "Junior":
      return "L1 Supervised"
  }
}

const STATUS_ITEMS: AgentStatus[] = [
  "active",
  "idle",
  "warning",
  "error",
  "onboarding",
]
const STATUS_WEIGHTS = [60, 20, 10, 5, 5]

const ACTIVITY_ICONS: Record<ActivityEntry["type"], string> = {
  complete: "\u2705",
  receive: "\uD83D\uDCE5",
  tool: "\uD83D\uDD27",
  start: "\u25B6\uFE0F",
  submit: "\uD83D\uDCE4",
  flag: "\u26A0\uFE0F",
  approve: "\uD83D\uDC4D",
  delegate: "\u27A1\uFE0F",
}

const ACTIVITY_TYPES: ActivityEntry["type"][] = [
  "complete",
  "receive",
  "tool",
  "start",
  "submit",
  "flag",
  "approve",
  "delegate",
]

const CAREER_EVENT_TEMPLATES: {
  type: CareerEvent["type"]
  template: string
}[] = [
  { type: "hire", template: "Hired as {role}" },
  { type: "promote", template: "Promoted to {role}" },
  { type: "milestone", template: "Completed 50 tasks" },
  { type: "milestone", template: "Achieved 95% success rate" },
  { type: "trust-upgrade", template: "Trust upgraded to {autonomy}" },
  { type: "reassign", template: "Reassigned to {dept} department" },
  { type: "milestone", template: "First solo project delivered" },
]

function generateTimeString(
  rng: () => number,
  index: number,
): string {
  if (index < 3) {
    const hour = randInt(rng, 1, 12)
    const min = randInt(rng, 0, 59)
    const ampm = rng() > 0.5 ? "PM" : "AM"
    return `${hour}:${min.toString().padStart(2, "0")} ${ampm}`
  }
  if (index < 6) {
    const hour = randInt(rng, 1, 12)
    const min = randInt(rng, 0, 59)
    const ampm = rng() > 0.5 ? "PM" : "AM"
    return `Yesterday ${hour}:${min.toString().padStart(2, "0")} ${ampm}`
  }
  const daysAgo = randInt(rng, 2, 7)
  const hour = randInt(rng, 1, 12)
  const min = randInt(rng, 0, 59)
  const ampm = rng() > 0.5 ? "PM" : "AM"
  return `${daysAgo}d ago ${hour}:${min.toString().padStart(2, "0")} ${ampm}`
}

// ---------------------------------------------------------------------------
// Agent generation
// ---------------------------------------------------------------------------

function generateAgent(
  rng: () => number,
  name: string,
  id: string,
  shortName: string,
  role: string,
  department: string,
  level: Agent["level"],
  deptDef: DepartmentDef,
): Agent {
  const status = weightedPick(rng, STATUS_ITEMS, STATUS_WEIGHTS)
  const autonomyLevel = autonomyForLevel(level)

  // Hired date: random day in Jan-Mar 2026
  const hiredMonth = randInt(rng, 0, 2) // 0=Jan, 1=Feb, 2=Mar
  const maxDay = [31, 28, 15][hiredMonth] // Mar capped at 15 (before "today")
  const hiredDay = randInt(rng, 1, maxDay)
  const hiredDate = formatDate(hiredMonth, hiredDay, 2026)

  // Tenure affects task count: more tenure = more tasks
  const tenureMonths = 3 - hiredMonth
  const baseTasks = level === "C-Suite" || level === "VP" ? 40 : 10
  const tasksCompleted = randInt(
    rng,
    baseTasks,
    baseTasks + tenureMonths * 30 + 20,
  )

  const performance = {
    tasksCompleted,
    avgCompletionTime: randFloat(rng, 0.5, 8.0),
    successRate: randInt(rng, 70, 99),
    costEfficiency: randFloat(rng, 0.15, 3.5),
  }

  // Tools: 3-6 from department pool
  const toolCount = randInt(rng, 3, Math.min(6, deptDef.tools.length))
  const shuffledTools = [...deptDef.tools].sort(() => rng() - 0.5)
  const tools = shuffledTools.slice(0, toolCount)

  // Task history: 5-15 tasks
  const taskCount = randInt(rng, 5, 15)
  const taskHistory: TaskEntry[] = []
  for (let t = 0; t < taskCount; t++) {
    const taskName = pick(rng, deptDef.taskNames)
    const taskType = pick(rng, deptDef.taskTypes)
    taskHistory.push({
      id: `${id}-task-${t + 1}`,
      name: taskName,
      type: taskType,
      start: randInt(rng, 0, 72),
      duration: randFloat(rng, 0.5, 12),
      completed: rng() > 0.25,
    })
  }

  // Recent activity: 8-15 entries
  const activityCount = randInt(rng, 8, 15)
  const recentActivity: ActivityEntry[] = []
  for (let a = 0; a < activityCount; a++) {
    const actType = pick(rng, ACTIVITY_TYPES)
    const taskRef = pick(rng, deptDef.taskNames)
    let desc: string
    switch (actType) {
      case "complete":
        desc = `Completed "${taskRef}"`
        break
      case "receive":
        desc = `Received task "${taskRef}"`
        break
      case "tool":
        desc = `Invoked ${pick(rng, tools)} for "${taskRef}"`
        break
      case "start":
        desc = `Started working on "${taskRef}"`
        break
      case "submit":
        desc = `Submitted "${taskRef}" for review`
        break
      case "flag":
        desc = `Flagged issue in "${taskRef}"`
        break
      case "approve":
        desc = `Approved "${taskRef}"`
        break
      case "delegate":
        desc = `Delegated "${taskRef}"`
        break
    }
    recentActivity.push({
      time: generateTimeString(rng, a),
      type: actType,
      description: desc,
      icon: ACTIVITY_ICONS[actType],
    })
  }

  // Career timeline: 2-5 events (always starts with hire)
  const careerCount = randInt(rng, 2, 5)
  const careerTimeline: CareerEvent[] = [
    {
      date: hiredDate,
      event: `Hired as ${role}`,
      type: "hire",
    },
  ]
  for (let c = 1; c < careerCount; c++) {
    const tmpl = pick(rng, CAREER_EVENT_TEMPLATES.slice(1)) // skip hire template
    const eventMonth = Math.min(hiredMonth + c, 2)
    const eventDay = randInt(rng, 1, 28)
    careerTimeline.push({
      date: formatDate(eventMonth, eventDay, 2026),
      event: tmpl.template
        .replace("{role}", role)
        .replace("{autonomy}", autonomyLevel)
        .replace("{dept}", department),
      type: tmpl.type,
    })
  }

  return {
    id,
    name,
    shortName,
    role,
    department,
    level,
    status,
    autonomyLevel,
    hiredDate,
    performance,
    tools,
    taskHistory,
    recentActivity,
    careerTimeline,
  }
}

// ---------------------------------------------------------------------------
// Build full agent roster
// ---------------------------------------------------------------------------

function buildAgents(): Agent[] {
  const rng = createRng(42)
  const result: Agent[] = []
  let nameIndex = 0

  // CEO first
  const ceoName = NAMES[nameIndex++]
  result.push(
    generateAgent(
      rng,
      ceoName,
      "ceo",
      "CEO",
      "Chief Executive Officer",
      "Executive",
      "C-Suite",
      {
        name: "Executive",
        roles: [],
        tools: [
          "analytics",
          "communication",
          "report_generation",
          "scheduling",
          "monitoring",
        ],
        taskNames: [
          "Strategic Vision Document",
          "Quarterly OKR Setting",
          "Board Meeting Preparation",
          "Company-wide Town Hall",
          "Executive Budget Review",
          "Partnership Strategy Brief",
          "Organizational Restructure Plan",
          "Investor Relations Update",
          "Crisis Response Protocol",
          "Annual Planning Kickoff",
          "Cross-functional Initiative Review",
          "Leadership Team Sync",
          "Culture & Values Refresh",
          "Market Expansion Analysis",
          "Talent Strategy Alignment",
        ],
        taskTypes: ["analysis", "report", "review", "operations"],
      },
    ),
  )

  // Track shortName counters to generate unique suffixes
  const shortNameCounters = new Map<string, number>()

  function nextShortName(prefix: string): string {
    const count = (shortNameCounters.get(prefix) ?? 0) + 1
    shortNameCounters.set(prefix, count)
    // For prefixes that have only one instance (VP roles, unique roles), no number
    return count === 1 ? prefix : `${prefix}-${count}`
  }

  // Process each department -- VPs first in each, then ICs
  // We'll collect VPs and ICs separately for sorting
  const vps: Agent[] = []
  const ics: Agent[] = []

  for (const dept of DEPARTMENTS) {
    for (const roleDef of dept.roles) {
      const name = NAMES[nameIndex++]

      // Build unique id
      const shortName = nextShortName(roleDef.shortPrefix)
      const id = shortName.toLowerCase().replace(/\s+/g, "-")

      const agent = generateAgent(
        rng,
        name,
        id,
        shortName,
        roleDef.role,
        dept.name,
        roleDef.level,
        dept,
      )

      if (roleDef.level === "VP" || roleDef.level === "C-Suite") {
        vps.push(agent)
      } else {
        ics.push(agent)
      }
    }
  }

  // Sort VPs alphabetically by department name
  vps.sort((a, b) => a.department.localeCompare(b.department))

  // Sort ICs by department name, then by level order, then by name
  const levelOrder: Record<Agent["level"], number> = {
    "C-Suite": 0,
    VP: 1,
    Lead: 2,
    Senior: 3,
    Mid: 4,
    Junior: 5,
  }
  ics.sort((a, b) => {
    const deptCmp = a.department.localeCompare(b.department)
    if (deptCmp !== 0) return deptCmp
    const lvlCmp = levelOrder[a.level] - levelOrder[b.level]
    if (lvlCmp !== 0) return lvlCmp
    return a.name.localeCompare(b.name)
  })

  return [...result, ...vps, ...ics]
}

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

export const agents: Agent[] = buildAgents()

export function getAgent(id: string): Agent | undefined {
  return agents.find((a) => a.id === id)
}
