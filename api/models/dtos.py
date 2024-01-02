from pydantic import BaseModel

class InputLink(BaseModel):
    link_product: str = None
    link_path: str = None