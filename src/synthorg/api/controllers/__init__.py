"""API controllers for all resource groups."""

from litestar import Controller

from synthorg.api.auth.controller import AuthController
from synthorg.api.controllers.activities import ActivityController
from synthorg.api.controllers.agents import AgentController
from synthorg.api.controllers.analytics import AnalyticsController
from synthorg.api.controllers.approvals import ApprovalsController
from synthorg.api.controllers.artifacts import ArtifactController
from synthorg.api.controllers.autonomy import AutonomyController
from synthorg.api.controllers.backup import BackupController
from synthorg.api.controllers.budget import BudgetController
from synthorg.api.controllers.ceremony_policy import (
    CeremonyPolicyController,
)
from synthorg.api.controllers.collaboration import CollaborationController
from synthorg.api.controllers.company import CompanyController
from synthorg.api.controllers.coordination import CoordinationController
from synthorg.api.controllers.departments import DepartmentController
from synthorg.api.controllers.health import HealthController
from synthorg.api.controllers.meetings import MeetingController
from synthorg.api.controllers.memory import MemoryAdminController
from synthorg.api.controllers.messages import MessageController
from synthorg.api.controllers.personalities import (
    PersonalityPresetController,
)
from synthorg.api.controllers.projects import ProjectController
from synthorg.api.controllers.providers import ProviderController
from synthorg.api.controllers.quality import QualityController
from synthorg.api.controllers.settings import SettingsController
from synthorg.api.controllers.setup import SetupController
from synthorg.api.controllers.setup_personality import (
    SetupPersonalityController,
)
from synthorg.api.controllers.tasks import TaskController
from synthorg.api.controllers.template_packs import TemplatePackController
from synthorg.api.controllers.users import UserController
from synthorg.api.controllers.workflow_executions import (
    WorkflowExecutionController,
)
from synthorg.api.controllers.workflows import WorkflowController
from synthorg.api.controllers.ws import ws_handler

ALL_CONTROLLERS: tuple[type[Controller], ...] = (
    HealthController,
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
    SettingsController,
    SetupController,
    SetupPersonalityController,
    PersonalityPresetController,
    BackupController,
    MemoryAdminController,
    TemplatePackController,
    UserController,
    WorkflowController,
    QualityController,
    WorkflowExecutionController,
)

__all__ = [
    "ALL_CONTROLLERS",
    "ActivityController",
    "AgentController",
    "AnalyticsController",
    "ApprovalsController",
    "ArtifactController",
    "AuthController",
    "AutonomyController",
    "BackupController",
    "BudgetController",
    "CeremonyPolicyController",
    "CollaborationController",
    "CompanyController",
    "Controller",
    "CoordinationController",
    "DepartmentController",
    "HealthController",
    "MeetingController",
    "MemoryAdminController",
    "MessageController",
    "PersonalityPresetController",
    "ProjectController",
    "ProviderController",
    "QualityController",
    "SettingsController",
    "SetupController",
    "SetupPersonalityController",
    "TaskController",
    "TemplatePackController",
    "UserController",
    "WorkflowController",
    "WorkflowExecutionController",
    "ws_handler",
]
