"""API controllers for all resource groups."""

from litestar import Controller

from synthorg.api.auth.controller import AuthController
from synthorg.api.controllers.activities import ActivityController
from synthorg.api.controllers.agents import AgentController
from synthorg.api.controllers.analytics import AnalyticsController
from synthorg.api.controllers.approvals import ApprovalsController
from synthorg.api.controllers.artifacts import ArtifactController
from synthorg.api.controllers.audit import AuditController
from synthorg.api.controllers.autonomy import AutonomyController
from synthorg.api.controllers.backup import BackupController
from synthorg.api.controllers.budget import BudgetController
from synthorg.api.controllers.budget_config_versions import (
    BudgetConfigVersionController,
)
from synthorg.api.controllers.ceremony_policy import (
    CeremonyPolicyController,
)
from synthorg.api.controllers.clients import ClientController
from synthorg.api.controllers.collaboration import CollaborationController
from synthorg.api.controllers.company import CompanyController
from synthorg.api.controllers.company_versions import (
    CompanyVersionController,
)
from synthorg.api.controllers.connections import ConnectionsController
from synthorg.api.controllers.coordination import CoordinationController
from synthorg.api.controllers.coordination_metrics import (
    CoordinationMetricsController,
)
from synthorg.api.controllers.departments import DepartmentController
from synthorg.api.controllers.evaluation_config_versions import (
    EvaluationConfigVersionController,
)
from synthorg.api.controllers.health import HealthController
from synthorg.api.controllers.integration_health import (
    IntegrationHealthController,
)
from synthorg.api.controllers.mcp_catalog import MCPCatalogController
from synthorg.api.controllers.meetings import MeetingController
from synthorg.api.controllers.memory import MemoryAdminController
from synthorg.api.controllers.messages import MessageController
from synthorg.api.controllers.metrics import MetricsController
from synthorg.api.controllers.oauth import OAuthController
from synthorg.api.controllers.ontology import OntologyController
from synthorg.api.controllers.personalities import (
    PersonalityPresetController,
)
from synthorg.api.controllers.projects import ProjectController
from synthorg.api.controllers.providers import ProviderController
from synthorg.api.controllers.quality import QualityController
from synthorg.api.controllers.reports import ReportsController
from synthorg.api.controllers.requests import RequestController
from synthorg.api.controllers.reviews import ReviewController
from synthorg.api.controllers.role_versions import RoleVersionController
from synthorg.api.controllers.scaling import ScalingController
from synthorg.api.controllers.settings import SettingsController
from synthorg.api.controllers.setup import SetupController
from synthorg.api.controllers.setup_personality import (
    SetupPersonalityController,
)
from synthorg.api.controllers.simulations import SimulationController
from synthorg.api.controllers.subworkflows import SubworkflowController
from synthorg.api.controllers.tasks import TaskController
from synthorg.api.controllers.teams import TeamController
from synthorg.api.controllers.template_packs import TemplatePackController
from synthorg.api.controllers.training import TrainingController
from synthorg.api.controllers.tunnel import TunnelController
from synthorg.api.controllers.users import UserController
from synthorg.api.controllers.webhooks import WebhooksController
from synthorg.api.controllers.workflow_executions import (
    WorkflowExecutionController,
)
from synthorg.api.controllers.workflow_versions import (
    WorkflowVersionController,
)
from synthorg.api.controllers.workflows import WorkflowController
from synthorg.api.controllers.ws import ws_handler

# Core API controllers (always registered).
BASE_CONTROLLERS: tuple[type[Controller], ...] = (
    HealthController,
    MetricsController,
    CompanyController,
    AgentController,
    ActivityController,
    DepartmentController,
    ProjectController,
    TaskController,
    MessageController,
    MeetingController,
    ArtifactController,
    BudgetController,
    AnalyticsController,
    ProviderController,
    ApprovalsController,
    AutonomyController,
    AuthController,
    CollaborationController,
    CeremonyPolicyController,
    CoordinationController,
    AuditController,
    CoordinationMetricsController,
    SettingsController,
    SetupController,
    SetupPersonalityController,
    PersonalityPresetController,
    BackupController,
    MemoryAdminController,
    TeamController,
    TemplatePackController,
    UserController,
    SubworkflowController,
    WorkflowController,
    WorkflowVersionController,
    BudgetConfigVersionController,
    CompanyVersionController,
    EvaluationConfigVersionController,
    RoleVersionController,
    QualityController,
    ReportsController,
    WorkflowExecutionController,
    OntologyController,
    ClientController,
    RequestController,
    SimulationController,
    ReviewController,
    ScalingController,
    TrainingController,
)

# Integration subsystem controllers. Registered only when
# ``effective_config.integrations.enabled`` is True (default in
# production, disabled in unit tests so Litestar route registration
# stays cheap -- ~0.7s per create_app() otherwise).
INTEGRATION_CONTROLLERS: tuple[type[Controller], ...] = (
    ConnectionsController,
    IntegrationHealthController,
    OAuthController,
    WebhooksController,
    MCPCatalogController,
    TunnelController,
)

ALL_CONTROLLERS: tuple[type[Controller], ...] = (
    *BASE_CONTROLLERS,
    *INTEGRATION_CONTROLLERS,
)

__all__ = [
    "ALL_CONTROLLERS",
    "BASE_CONTROLLERS",
    "INTEGRATION_CONTROLLERS",
    "ActivityController",
    "AgentController",
    "AnalyticsController",
    "ApprovalsController",
    "ArtifactController",
    "AuditController",
    "AuthController",
    "AutonomyController",
    "BackupController",
    "BudgetConfigVersionController",
    "BudgetController",
    "CeremonyPolicyController",
    "ClientController",
    "CollaborationController",
    "CompanyController",
    "CompanyVersionController",
    "ConnectionsController",
    "Controller",
    "CoordinationController",
    "CoordinationMetricsController",
    "DepartmentController",
    "EvaluationConfigVersionController",
    "HealthController",
    "IntegrationHealthController",
    "MCPCatalogController",
    "MeetingController",
    "MemoryAdminController",
    "MessageController",
    "MetricsController",
    "OAuthController",
    "OntologyController",
    "PersonalityPresetController",
    "ProjectController",
    "ProviderController",
    "QualityController",
    "ReportsController",
    "RequestController",
    "ReviewController",
    "RoleVersionController",
    "ScalingController",
    "SettingsController",
    "SetupController",
    "SetupPersonalityController",
    "SimulationController",
    "SubworkflowController",
    "TaskController",
    "TeamController",
    "TemplatePackController",
    "TrainingController",
    "TunnelController",
    "UserController",
    "WebhooksController",
    "WorkflowController",
    "WorkflowExecutionController",
    "WorkflowVersionController",
    "ws_handler",
]
