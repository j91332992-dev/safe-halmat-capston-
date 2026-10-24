"""Stage counters locate loss boundaries; they do not diagnose RF physics."""
STAGES = (
    'slot_tx','slot_rx','attempt','poll_tx','response_rx','response_tx',
    'final_tx','final_rx','result_tx','result_rx','distance_ok',
    'relay_tx','relay_rx','rx_timeout','rx_error','frame_mismatch',
    'tx_error','cia_error','tx_timestamp_error','interval_error',
    'distance_error','relay_error','unexpected_rx','ss_attempt',
)


def summarize_trace(records):
    rows=[]
    for r in records:
        row=dict(r)
        row['counters']=dict(zip(STAGES,row.pop('counts')))
        rows.append(row)
    boundaries=[]
    index={(r['anchor'],r['a'],r['b']):r for r in rows}
    for a,b in ((1,2),(1,3),(1,4),(2,3),(2,4),(3,4)):
        initiator=index.get((a,a,b));responder=index.get((b,a,b));master=index.get((1,a,b))
        missing=[n for n,r in [('initiator',initiator),('responder',responder),('coordinator',master)]
                 if not r or not r['received']]
        findings=[]
        i=initiator['counters'] if initiator and initiator['received'] else None
        r=responder['counters'] if responder and responder['received'] else None
        m=master['counters'] if master and master['received'] else None
        if missing:findings.append('diagnostic_report_missing')
        if a!=1 and i is not None and m is not None and m['slot_tx'] and not i['slot_rx']:
            findings.append('slot_not_received')
        if i is not None and r is not None and i['poll_tx'] and not r['attempt']:
            findings.append('poll_not_observed_by_responder')
        if i is not None and i['rx_timeout']:findings.append('initiator_rx_timeout')
        if r is not None and r['tx_error']:findings.append('responder_tx_error')
        if i is not None and r is not None and i['final_tx'] and not r['final_rx']:
            findings.append('final_not_observed_by_responder')
        if i is not None and i['distance_error']:findings.append('distance_out_of_range')
        if i is not None and i['interval_error']:findings.append('timestamp_interval_invalid')
        if a!=1 and i is not None and m is not None and i['relay_tx']>m['relay_rx']:
            findings.append('relay_reports_missing_at_coordinator')
        if any(x and x['counters']['frame_mismatch'] for x in (initiator,responder) if x and x['received']):
            findings.append('frame_mismatch')
        boundaries.append(dict(pair=f'{a}-{b}',missing_reports=missing,findings=findings))
    return dict(version=1,records=rows,pairs=boundaries,
                notice='Counters identify observed loss stages; missing reports are unknown, not zero. RF cause requires further evidence.')
