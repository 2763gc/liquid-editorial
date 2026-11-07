from pydantic import BaseModel, ConfigDict

class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    color: str | None = None
    description: str | None = None
