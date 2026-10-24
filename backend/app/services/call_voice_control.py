"""Bounded, best-effort control recognition alongside (never inside) call relay."""
import asyncio
import io
import logging
import re
import wave
from time import monotonic

import numpy as np

from ..config import settings
from .whisper_service import _get_client
from .voice_trace import record_voice


class CallVoiceControl:
    def __init__(self, end_call):
        self.end_call = end_call
        self.sessions = {}
        self.inflight = 0

    def start(self, device_id):
        self.stop(device_id)
        if not settings.call_voice_end_enabled:
            return
        state = dict(buffer=bytearray(), pre=bytearray(), silence=0, voiced=0,
                     pending=None, wake=asyncio.Event(), last_packet=0,
                     metrics=dict(clips=0, replaced=0, busy=0, stale=0,
                                  requests=0, errors=0, matched=0,
                                  uploaded_bytes=0, max_stt_ms=0.0))
        self.sessions[device_id] = state
        state['task'] = asyncio.create_task(self._run(device_id, state))

    def stop(self, device_id):
        state = self.sessions.pop(device_id, None)
        if state:
            if state['task'] is not asyncio.current_task():
                state['task'].cancel()
            record_voice('call_control_summary', device_id, **state['metrics'])

    def diagnostics(self, device_id):
        state = self.sessions.get(device_id)
        return dict(state['metrics'], buffer_bytes=len(state['buffer']),
                    pending_clips=int(state['pending'] is not None)) if state else {}

    def feed(self, device_id, pcm):
        state = self.sessions.get(device_id)
        if not state or not settings.use_whisper_stt or not settings.openai_api_key:
            return
        now = monotonic()
        # Never splice speech across a network outage.
        if now - state['last_packet'] > 0.5:
            state['buffer'].clear()
            state['pre'].clear()
            state['silence'] = state['voiced'] = 0
        state['last_packet'] = now
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32)
        speech = float(np.sqrt(np.mean(samples * samples))) >= settings.call_voice_end_rms
        if not state['buffer']:
            if not speech:
                state['pre'].extend(pcm)
                del state['pre'][:-6400]  # 200ms pre-roll
                return
            state['buffer'].extend(state['pre'])
            state['pre'].clear()
        state['buffer'].extend(pcm)
        state['silence'] = 0 if speech else state['silence'] + len(pcm)
        if speech:
            state['voiced'] += len(pcm)
        silence_end = state['silence'] >= 11200  # 350ms
        if len(state['buffer']) < 96000 and not silence_end:
            return
        if state['voiced'] >= 9600:  # reject impulses shorter than 300ms
            if state['pending'] is not None:
                state['metrics']['replaced'] += 1
            state['pending'] = (bytes(state['buffer']), now)
            state['metrics']['clips'] += 1
            state['wake'].set()
        tail = state['buffer'][-32000:] if not silence_end else bytearray()
        state['buffer'] = bytearray(tail)  # 1s overlap for continuous speech
        state['voiced'] = 0
        state['silence'] = 0

    @staticmethod
    def is_end_command(text):
        # Full utterances only: no substring matching of '중단', quoted requests,
        # or negatives such as '통화 종료하지 마'.
        text = re.sub(r'[^가-힣]', '', text)
        return text in {'통화종료', '통화종료해', '통화종료해줘', '통화종료해주세요',
                        '통화종료해줘요', '전화끊어', '전화끊어줘', '전화끊어주세요',
                        '통화끊어줘', '통화끝내줘', '통화끝내주세요'}

    async def _run(self, device_id, state):
        try:
            while self.sessions.get(device_id) is state:
                await state['wake'].wait()
                state['wake'].clear()
                pending, state['pending'] = state['pending'], None
                if pending is None:
                    continue
                pcm, captured = pending
                stats = state['metrics']
                if monotonic() - captured > 1.5:
                    stats['stale'] += 1
                    continue
                if self.inflight >= 2:
                    stats['busy'] += 1
                    continue
                self.inflight += 1
                started = monotonic()
                matched = False
                outcome = 'not_matched'
                try:
                    wav = io.BytesIO()
                    with wave.open(wav, 'wb') as out:
                        out.setnchannels(1)
                        out.setsampwidth(2)
                        out.setframerate(16000)
                        out.writeframes(pcm)
                    data = wav.getvalue()
                    stats['requests'] += 1
                    stats['uploaded_bytes'] += len(data)
                    request = dict(model=settings.stt_model,
                                   file=('call-control.wav', data, 'audio/wav'))
                    if settings.stt_model == 'gpt-transcribe':
                        request['extra_body'] = {'languages': [settings.stt_language]}
                    else:
                        request['language'] = settings.stt_language
                    async with asyncio.timeout(4.0):
                        result = await _get_client().audio.transcriptions.create(**request)
                    matched = self.is_end_command(result if isinstance(result, str) else getattr(result, 'text', ''))
                    outcome = 'matched' if matched else 'not_matched'
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    stats['errors'] += 1
                    outcome = type(exc).__name__
                finally:
                    self.inflight -= 1
                    stats['max_stt_ms'] = max(stats['max_stt_ms'], round((monotonic()-started)*1000, 1))
                record_voice('call_control', device_id, outcome=outcome,
                             stt_ms=round((monotonic()-started)*1000, 1),
                             audio_ms=round(len(pcm)/32), **stats)
                if self.sessions.get(device_id) is not state:
                    return  # a late result must not terminate a subsequent call
                if matched:
                    stats['matched'] += 1
                    await self.end_call(device_id)
                    return
                await asyncio.sleep(max(0, (5.0 if outcome not in {'matched', 'not_matched'} else 1.0)
                                        - (monotonic()-started)))
        except asyncio.CancelledError:
            pass
        except Exception:
            logging.exception('Call voice control stopped device=%s', device_id)
