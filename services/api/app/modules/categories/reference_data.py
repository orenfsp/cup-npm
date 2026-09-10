from dataclasses import dataclass

UNKNOWN_CATEGORY_SLUG = "unsure"


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    slug: str
    name: str
    description: str
    sort_order: int


@dataclass(frozen=True, slots=True)
class IntakeQuestionDefinition:
    id: str
    prompt_student: str
    prompt_formal: str
    max_length: int = 1000


STARTER_CATEGORIES = (
    CategoryDefinition(
        "bullying-insults", "Буллинг и оскорбления", "Травля, унижение или оскорбления.", 10
    ),
    CategoryDefinition(
        "classmate-conflict",
        "Конфликт с одноклассниками",
        "Сложная ситуация со сверстниками.",
        20,
    ),
    CategoryDefinition(
        "cyberbullying", "Кибербуллинг", "Травля или преследование в интернете.", 30
    ),
    CategoryDefinition("pressure-threats", "Давление и угрозы", "Давление, шантаж или угрозы.", 40),
    CategoryDefinition(
        "teacher-conflict", "Конфликт с учителем", "Сложная ситуация с педагогом.", 50
    ),
    CategoryDefinition("parent-conflict", "Конфликт с родителями", "Сложная ситуация в семье.", 60),
    CategoryDefinition(
        "legal-question", "Юридический вопрос", "Вопрос о правах и возможных действиях.", 70
    ),
    CategoryDefinition(
        UNKNOWN_CATEGORY_SLUG,
        "Не знаю, как это назвать",
        "Можно просто описать ситуацию своими словами.",
        80,
    ),
)

INTAKE_QUESTIONS = (
    IntakeQuestionDefinition("where", "Где это происходит?", "Где это происходит?"),
    IntakeQuestionDefinition("duration", "Как давно это происходит?", "Как давно это происходит?"),
    IntakeQuestionDefinition("involved", "Кто участвует?", "Кто участвует?"),
    IntakeQuestionDefinition(
        "help_requested",
        "Ты уже просил(а) кого-нибудь о помощи?",
        "Вы уже просили кого-нибудь о помощи?",
    ),
)

INTAKE_QUESTION_IDS = frozenset(question.id for question in INTAKE_QUESTIONS)


@dataclass(frozen=True, slots=True)
class ApplicantTypeDefinition:
    code: str
    label: str
    description: str
    tone: str
    sort_order: int


APPLICANT_TYPES = (
    ApplicantTypeDefinition("student", "Ученик", "Обращение от ученика", "informal", 10),
    ApplicantTypeDefinition("parent", "Родитель", "Обращение от родителя", "formal", 20),
    ApplicantTypeDefinition("teacher", "Учитель", "Обращение от учителя", "formal", 30),
)
