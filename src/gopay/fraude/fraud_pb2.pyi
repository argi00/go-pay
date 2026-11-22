from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class TransfertRequest(_message.Message):
    __slots__ = ("wallet_id", "montant", "beneficiaire_tel", "region")
    WALLET_ID_FIELD_NUMBER: _ClassVar[int]
    MONTANT_FIELD_NUMBER: _ClassVar[int]
    BENEFICIAIRE_TEL_FIELD_NUMBER: _ClassVar[int]
    REGION_FIELD_NUMBER: _ClassVar[int]
    wallet_id: int
    montant: int
    beneficiaire_tel: str
    region: str
    def __init__(self, wallet_id: _Optional[int] = ..., montant: _Optional[int] = ..., beneficiaire_tel: _Optional[str] = ..., region: _Optional[str] = ...) -> None: ...

class Verdict(_message.Message):
    __slots__ = ("score", "bloquer", "raison")
    SCORE_FIELD_NUMBER: _ClassVar[int]
    BLOQUER_FIELD_NUMBER: _ClassVar[int]
    RAISON_FIELD_NUMBER: _ClassVar[int]
    score: float
    bloquer: bool
    raison: str
    def __init__(self, score: _Optional[float] = ..., bloquer: _Optional[bool] = ..., raison: _Optional[str] = ...) -> None: ...
