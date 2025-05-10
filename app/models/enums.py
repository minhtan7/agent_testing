import enum

# Enums
class UploadStatusEnum(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ContentTypeEnum(str, enum.Enum):
    text = "text"
    image = "image"
    table = "table"

class StudyPlanStatusEnum(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"

class SectionProgressStatusEnum(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"
    pending = "pending"

class MessageRoleEnum(str, enum.Enum):
    user = "user"
    ai = "ai"
    tool = "tool"

class SessionStatusEnum(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"

class StorageProvider(str, enum.Enum):
    """Where the binary object lives."""

    cloudinary = "cloudinary"
    s3 = "s3"
    gcs = "gcs"  # room for the future