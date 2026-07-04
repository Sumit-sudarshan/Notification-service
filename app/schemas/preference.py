from pydantic import BaseModel

from app.models.notification import ChannelEnum


class PreferenceUpdate(BaseModel):
    channel: ChannelEnum
    opted_in: bool


class PreferenceResponse(BaseModel):
    channel: ChannelEnum
    opted_in: bool

    model_config = {"from_attributes": True}
