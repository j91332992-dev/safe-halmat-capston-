import json
import math
import secrets
from typing import Literal
from hmac import compare_digest
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from typing import Annotated
from sqlalchemy.orm import Session

from ..config import BASE_DIR, settings
from ..database import get_db, utcnow
from ..models.entities import AnchorSurvey, LayoutDraft, SurveyCoordinator
from ..services.anchor_survey_service import ACTIVE, baseline, evaluate, expire, fire_active, object_issues, serialize
from ..services.uwb_log_service import BoundedJsonlLog
from .auth import require_site

router = APIRouter(prefix='/api/anchor-survey', tags=['anchor-survey'])
_audit = None
_coordinator_resources = {}  # Authenticated single-site device; transient runtime counters.


def audit(row, stage):
    global _audit
    if _audit is None:
        _audit = BoundedJsonlLog(BASE_DIR/'logs/anchor-survey.jsonl',2*1024*1024,3,7,60)
    _audit.append(dict(stage=stage,site_id=row.site_id,session_id=row.session_id,
        status=row.status,result=json.loads(row.result_json),samples=json.loads(row.samples_json) if stage=='completed' else None))


def device_site(authorization: str | None = Header(default=None)):
    expected = settings.uwb_survey_device_token
    supplied = authorization.removeprefix('Bearer ') if authorization else ''
    if not expected or not compare_digest(supplied,expected):
        raise HTTPException(401,'측량 장치 인증 실패')
    return settings.uwb_survey_site_id


def lookup(db, session_id, site_id):
    row = db.get(AnchorSurvey,session_id)
    if not row or row.site_id != site_id:
        raise HTTPException(404,'측량 세션이 없습니다.')
    return row


class StartIn(BaseModel):
    corners_confirmed: bool
    heights_confirmed: bool


@router.get('')
def status(site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    expire(db,site_id)
    coordinator = db.get(SurveyCoordinator,site_id)
    online = bool(coordinator and coordinator.protocol==1 and (utcnow()-coordinator.last_seen).total_seconds()<8)
    row = db.query(AnchorSurvey).filter(AnchorSurvey.site_id==site_id).order_by(AnchorSurvey.created_at.desc()).first()
    db.commit()
    return dict(supported=bool(online and settings.uwb_survey_device_token),
        coordinator_busy=bool(coordinator and coordinator.busy),
        coordinator_online=online, firmware=coordinator.firmware if coordinator else None,
        session=serialize(row),coordinator_resources=_coordinator_resources.get(site_id),
        notice='측량 중 UWB 위치가 잠시 중단됩니다. 결과는 승인 후에만 반영됩니다.')


@router.post('/start')
def start(payload: StartIn, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    expire(db,site_id)
    if not payload.corners_confirmed or not payload.heights_confirmed:
        raise HTTPException(400,'모서리 순서와 높이 설정을 확인하세요.')
    if fire_active(db,site_id):
        raise HTTPException(409,'화재 대응 중에는 측량할 수 없습니다.')
    coordinator = db.get(SurveyCoordinator,site_id)
    if not settings.uwb_survey_device_token or not coordinator or coordinator.protocol!=1 or (utcnow()-coordinator.last_seen).total_seconds()>=8:
        raise HTTPException(409,'측량 지원 앵커 1번 펌웨어 연결이 필요합니다.')
    if coordinator.busy:
        raise HTTPException(409,'앵커의 이전 측량 종료·복귀를 확인 중입니다. 잠시 후 다시 시도하세요.')
    if db.query(AnchorSurvey).filter(AnchorSurvey.site_id==site_id,AnchorSurvey.status.in_(ACTIVE)).first():
        raise HTTPException(409,'이미 측량 중입니다.')
    base = baseline(db,site_id)
    anchors = sorted(base['design']['anchors'],key=lambda a:a['anchor_id'])
    if len(anchors)!=4 or any(not math.isfinite(a['z']) for a in anchors):
        raise HTTPException(400,'정확히 4개 앵커와 유효한 높이 설정이 필요합니다.')
    base['design']['anchors'] = anchors
    row = AnchorSurvey(session_id=uuid4().hex,site_id=site_id,nonce=secrets.token_hex(16),
        status='requested',baseline_json=json.dumps(base,ensure_ascii=False))
    db.add(row);db.commit();audit(row,'requested')
    return serialize(row)


@router.post('/{session_id}/cancel')
def cancel(session_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    row=lookup(db,session_id,site_id)
    if row.status=='imported':
        raise HTTPException(409,'이미 설계안에 반영했습니다. 수동 편집으로 변경하세요.')
    row.status='cancelled';row.finished_at=utcnow();db.commit();audit(row,'cancelled')
    return serialize(row)


@router.post('/{session_id}/import')
def import_draft(session_id: str, site_id: str = Depends(require_site), db: Session = Depends(get_db)):
    db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    row=lookup(db,session_id,site_id)
    if row.status!='ready' or (utcnow()-row.created_at).total_seconds()>600:
        raise HTTPException(409,'등록 가능한 최신 측량 결과가 아닙니다.')
    if fire_active(db,site_id):
        raise HTTPException(409,'화재 대응 중에는 지도를 변경할 수 없습니다.')
    old=json.loads(row.baseline_json);live=baseline(db,site_id)
    if old['current']!=live['current'] or old['draft']!=live['draft']:
        raise HTTPException(409,'측정 후 지도/설계안이 바뀌었습니다. 다시 측정하세요.')
    result=json.loads(row.result_json)
    if not result.get('passed'):
        raise HTTPException(409,'측량 품질 검증을 통과하지 못했습니다.')
    design=live['design'];design['site'].update(width=result['width'],height=result['height'])
    points=[(0,0),(result['width'],0),(result['width'],result['height']),(0,result['height'])]
    for anchor,(x,y) in zip(sorted(design['anchors'],key=lambda a:a['anchor_id']),points):
        anchor.update(x=x,y=y)
    draft=db.get(LayoutDraft,site_id)
    if not draft:
        draft=LayoutDraft(site_id=site_id,draft_json='{}');db.add(draft)
    draft.draft_json=json.dumps(design,ensure_ascii=False);draft.updated_at=utcnow()
    row.status='imported';db.commit();audit(row,'draft_imported')
    return dict(draft={**design,'saved_at':draft.updated_at.isoformat()+'Z'},issues=object_issues(design))


class PollIn(BaseModel):
    protocol: int
    firmware: str = Field(max_length=80)
    busy: bool = False
    heap_free_bytes: int | None = Field(default=None,ge=0,le=1048576)
    heap_min_bytes: int | None = Field(default=None,ge=0,le=1048576)
    stack_high_watermark_raw: int | None = Field(default=None,ge=0,le=1048576)


@router.post('/device/poll')
def poll(payload: PollIn, site_id: str = Depends(device_site), db: Session = Depends(get_db)):
    expire(db,site_id)
    c=db.get(SurveyCoordinator,site_id)
    if not c:
        c=SurveyCoordinator(site_id=site_id,protocol=payload.protocol,firmware=payload.firmware);db.add(c)
    c.protocol=payload.protocol;c.firmware=payload.firmware;c.last_seen=utcnow()
    c.busy=payload.busy
    if payload.heap_free_bytes is not None:
        _coordinator_resources[site_id]=dict(heap_free_bytes=payload.heap_free_bytes,
            heap_min_bytes=payload.heap_min_bytes,stack_high_watermark_raw=payload.stack_high_watermark_raw,
            recorded_at=utcnow().isoformat()+'Z')
    row=db.query(AnchorSurvey).filter(AnchorSurvey.site_id==site_id,AnchorSurvey.status.in_(ACTIVE)).first()
    db.commit()
    return dict(command='survey' if row and payload.protocol==1 else 'idle',
        session_id=row.session_id if row else '',nonce=row.nonce if row else '',duration_ms=10000)


class ReadyIn(BaseModel):
    nonce: str = Field(max_length=40)
    ready_mask: int


@router.post('/device/{session_id}/begin')
def begin(session_id: str, payload: ReadyIn, site_id: str = Depends(device_site), db: Session = Depends(get_db)):
    expire(db,site_id);row=lookup(db,session_id,site_id)
    if not compare_digest(row.nonce,payload.nonce) or row.status not in ACTIVE or payload.ready_mask!=15:
        raise HTTPException(409,'앵커 준비/세션 상태가 유효하지 않습니다.')
    if row.status=='requested':
        row.status='measuring';row.started_at=utcnow();db.commit();audit(row,'measuring')
    return dict(measure_ms=10000)


class Sample(BaseModel):
    a: int = Field(ge=1,le=4)
    b: int = Field(ge=1,le=4)
    sequence: int = Field(ge=0,le=255)
    elapsed_ms: int = Field(ge=0,lt=10000)
    distance_m: float = Field(gt=0,le=100,allow_inf_nan=False)
    diagnostic_valid: bool
    gap_db: float = Field(allow_inf_nan=False)
    path_samples: float = Field(allow_inf_nan=False)
    poll_tx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)
    response_rx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)
    remote_poll_rx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)
    remote_response_tx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)
    clock_offset_raw: int | None = Field(default=None,ge=-32768,le=32767)
    sys_status: int | None = Field(default=None,ge=0,le=0xffffffff)
    ranging_method: Literal['ss-twr','ds-twr'] | None = None
    final_tx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)
    remote_final_rx_dtu_low32: int | None = Field(default=None,ge=0,le=0xffffffff)


class CompleteIn(BaseModel):
    nonce: str = Field(max_length=40)
    completed: bool
    duration_ms: int = Field(ge=0,le=12000)
    samples: list[Sample] = Field(max_length=240)
    error: str = Field(default='',max_length=100)
    stage_diagnostics: list['StageDiagnostic'] = Field(default_factory=list,max_length=15)

    @model_validator(mode='after')
    def unique_stage_records(self):
        keys=[(r.anchor,r.a,r.b) for r in self.stage_diagnostics]
        if len(keys)!=len(set(keys)):raise ValueError('duplicate stage diagnostic')
        return self


class StageDiagnostic(BaseModel):
    anchor: int = Field(ge=1,le=4)
    a: int = Field(ge=1,le=3)
    b: int = Field(ge=2,le=4)
    version: Literal[1]
    received: bool
    counts: list[Annotated[int,Field(ge=0,le=255)]] = Field(min_length=24,max_length=24)
    last_status: int = Field(ge=0,le=0xffffffff)
    last_function: int = Field(ge=0,le=255)
    last_distance: float | None = Field(default=None,allow_inf_nan=False)

    @model_validator(mode='after')
    def valid_pair(self):
        if self.a>=self.b or self.anchor not in (1,self.a,self.b):raise ValueError('invalid trace pair')
        return self


CompleteIn.model_rebuild()


@router.post('/device/{session_id}/complete')
def complete(session_id: str, payload: CompleteIn, site_id: str = Depends(device_site), db: Session = Depends(get_db)):
    expire(db,site_id);row=lookup(db,session_id,site_id)
    if not compare_digest(row.nonce,payload.nonce):
        raise HTTPException(403,'측량 nonce가 다릅니다.')
    if row.status in ('ready','rejected'):
        return serialize(row)  # retry is idempotent, never overwrite a result
    if row.status not in ACTIVE:
        raise HTTPException(409,'종료되거나 취소된 측량입니다.')
    samples=[s.model_dump() for s in payload.samples]
    valid_time=bool(row.started_at and (utcnow()-row.started_at).total_seconds()>=9)
    if not payload.completed or not valid_time or not 9500<=payload.duration_ms<=11000:
        result=dict(passed=False,reasons=[payload.error or '10초 측정이 완료되지 않았습니다.'])
    else:
        result=evaluate(samples,json.loads(row.baseline_json)['design']['anchors'])
    if payload.stage_diagnostics:
        from ..services.anchor_survey_trace import summarize_trace
        result['stage_diagnostics']=summarize_trace([r.model_dump() for r in payload.stage_diagnostics])
    row.samples_json=json.dumps(samples);row.result_json=json.dumps(result,ensure_ascii=False)
    row.status='ready' if result['passed'] else 'rejected';row.finished_at=utcnow()
    db.commit();audit(row,'completed')
    return serialize(row)
