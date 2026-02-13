from pydantic import BaseModel


class SettingsOut(BaseModel):
    app_name: str
    app_env: str
    theme: str = "system"
    locale: str = "en"
