import type {Worker} from '../types';

export function positionTimestamp(worker: Worker): number {
  const status=worker.position_status;
  for(const value of [status?.server_received_at,status?.last_valid_at,worker.updated_at]){
    if(!value)continue;
    const normalized=/(?:Z|[+-]\d\d:\d\d)$/.test(value)?value:value+'Z';
    const time=Date.parse(normalized);
    if(Number.isFinite(time))return time;
  }
  return 0;
}

// Snapshot HTTP responses and live WS updates can arrive in either order.
// Preserve only newer position fields; still accept incoming PPE/risk metadata.
export function mergeWorkerPosition(incoming: Worker,current?: Worker): Worker {
  if(!current||current.worker_id!==incoming.worker_id)return incoming;
  if(positionTimestamp(incoming)>=positionTimestamp(current))return incoming;
  return {...incoming,x:current.x,y:current.y,confidence:current.confidence,
    current_zone:current.current_zone,position_status:current.position_status};
}
