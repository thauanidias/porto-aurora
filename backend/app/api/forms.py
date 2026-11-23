from fastapi import APIRouter

from app.api.admin import OrgInput, UserInput
from app.api.assessments import AssessmentInput, AssignInput
from app.api.candidates import PoolInput
from app.api.interviews import EvaluationInput, InterviewInput
from app.api.offers import OfferInput
from app.api.operations import TaskInput
from app.core.permissions import Current
from app.schemas.auth import StrictModel
from app.schemas.recruitment import PipelineInput, RequestInput, ScoreInput, VacancyInput

router = APIRouter(tags=["Formulários"])
FORMS: dict[str, tuple[str, type[StrictModel]]] = {
    "request": ("request.create", RequestInput),
    "vacancy": ("vacancy.create", VacancyInput),
    "scoring": ("score.manage", ScoreInput),
    "pipeline": ("vacancy.edit", PipelineInput),
    "org": ("org.manage", OrgInput),
    "user": ("user.manage", UserInput),
    "test": ("test.manage", AssessmentInput),
    "test-assignment": ("test.manage", AssignInput),
    "interview": ("interview.manage", InterviewInput),
    "evaluation": ("interview.manage", EvaluationInput),
    "offer": ("offer.create", OfferInput),
    "task": ("task.manage", TaskInput),
    "pool": ("talent.manage", PoolInput),
}


@router.get("/forms/{name}")
def form(name: str, actor: Current):
    from app.core.errors import DomainError

    if name not in FORMS:
        raise DomainError("Formulário não encontrado.", 404)
    permission, schema = FORMS[name]
    actor.require(permission)
    return schema.model_json_schema()
