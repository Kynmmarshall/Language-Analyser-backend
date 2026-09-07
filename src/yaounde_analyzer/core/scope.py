from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

TARGET_VARIETY: Final = "cameroon_francanglais"
MAX_INPUT_CHARACTERS: Final = 2000
TargetVariety = Literal["cameroon_francanglais"]


class FrancanglaisModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_variety: TargetVariety = TARGET_VARIETY