#pragma once
// Included after anchor.cpp radio constants/helpers. Normal builds do not use it.
#include "uwb_diagnostics.h"
#include "survey_trace.h"
#if ANCHOR_ID == MASTER_ANCHOR_ID
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "wifi_secrets.h"
#include "wifi_profiles.h"
#ifndef HANMIR_SURVEY_TOKEN
#define HANMIR_SURVEY_TOKEN ""
#endif
#endif

enum { SURVEY_CONTROL=0xE4, SURVEY_READY=0xE5, SURVEY_SLOT=0xE6,
       SURVEY_POLL=0xE7, SURVEY_RESPONSE=0xE8, SURVEY_RESULT=0xE9,
       SURVEY_DS_POLL=0xEA,SURVEY_DS_RESPONSE=0xEB,SURVEY_DS_FINAL=0xEC,SURVEY_DS_RESULT=0xED,
       SURVEY_TRACE_POLL=0xEE,SURVEY_TRACE_RESPONSE=0xEF };
static constexpr unsigned SURVEY_MAX_SAMPLES=108; // <=100 slots in a 10s/100ms window.
struct SurveySample {uint8_t a,b,sequence; uint16_t elapsed; float distance,gap,path; bool valid;
    bool raw_present; uint32_t poll_tx,response_rx,remote_poll_rx,remote_response_tx,rx_status; int16_t clock_raw;
    bool ds; uint32_t final_tx,remote_final_rx;};
struct SurveyCommand {uint8_t kind; char session[33],nonce[33];};
struct SurveyResult {bool prepared,completed; SurveyCommand context; uint16_t duration,count;
                     uint8_t ready; char error[48]; SurveySample samples[SURVEY_MAX_SAMPLES];
                     uint8_t trace_count; SurveyTrace traces[15];};
static uint32_t survey_token=0,survey_deadline=0,survey_created=0,survey_measure_at=0,survey_last_slot=0;
static uint8_t survey_mask=0,survey_sequence=0;
static uint8_t survey_ds_mask=1;
static bool survey_ds_mode=false;
static const uint8_t survey_pairs[6][2]={{0xA0,0xA1},{0xA0,0xA2},{0xA0,0xA3},{0xA1,0xA2},{0xA1,0xA3},{0xA2,0xA3}};
static bool survey_measuring=false,survey_prepared=false;
static SurveyResult survey_result;
static QueueHandle_t survey_commands=nullptr,survey_results=nullptr;
static uint32_t survey_u32(const uint8_t *p){uint32_t v;memcpy(&v,p,4);return v;}
static void survey_put32(uint8_t *p,uint32_t v){memcpy(p,&v,4);}
static bool survey_active(){return survey_token!=0;}
static SurveyTrace survey_traces[6];
static uint32_t survey_trace_token=0;
static uint8_t survey_trace_pair=255;
static void survey_trace_reset(uint32_t token){
    memset(survey_traces,0,sizeof(survey_traces));survey_trace_token=token;survey_trace_pair=255;
    for(unsigned i=0;i<6;++i){auto &t=survey_traces[i];t.anchor=AIDX+1;
        t.a=survey_pairs[i][0]-0xA0+1;t.b=survey_pairs[i][1]-0xA0+1;t.received=true;t.last_distance=NAN;}
}
static void survey_trace_select(uint8_t a,uint8_t b){
    survey_trace_pair=255;
    for(unsigned i=0;i<6;++i)if(survey_pairs[i][0]==a&&survey_pairs[i][1]==b){survey_trace_pair=i;break;}
}
static void survey_trace_mark(SurveyStage stage){
    if(survey_trace_pair<6)survey_trace_increment(survey_traces[survey_trace_pair],stage);
}
static void survey_trace_status(uint32_t status,uint8_t function=0){
    if(survey_trace_pair<6){auto &t=survey_traces[survey_trace_pair];t.last_status=status;if(function)t.last_function=function;}
}
static void survey_trace_distance(double distance){
    if(survey_trace_pair<6)survey_traces[survey_trace_pair].last_distance=(float)distance;
}

static void survey_frame(uint8_t *b,size_t n,uint8_t func,uint16_t dst,uint8_t sequence){
    memset(b,0,n);b[0]=0x41;b[1]=0x88;b[2]=sequence;
    write_u16_le(b+3,NET_PAN_ID);write_u16_le(b+5,dst);write_u16_le(b+7,ANCHOR_ID);
    b[9]=func;survey_put32(b+10,survey_token);
}
static bool survey_send(uint8_t *b,size_t n,bool expect=false){
    dwt_forcetrxoff();
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_TXFRS_BIT_MASK|SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_ALL_RX_TO|SYS_STATUS_ALL_RX_ERR|SYS_STATUS_CIADONE_BIT_MASK);
    dwt_writetxdata(n,b,0);dwt_writetxfctrl(n,0,expect?1:0);
    if(dwt_starttx(DWT_START_TX_IMMEDIATE|(expect?DWT_RESPONSE_EXPECTED:0))!=DWT_SUCCESS)return false;
    uint32_t until=millis()+20;
    while(!(dwt_read32bitreg(SYS_STATUS_ID)&SYS_STATUS_TXFRS_BIT_MASK)){
        if((int32_t)(millis()-until)>=0){dwt_forcetrxoff();return false;}
        delayMicroseconds(20);
    }
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_TXFRS_BIT_MASK);return true;
}
static void survey_control(uint8_t phase){
    uint8_t b[22];survey_frame(b,sizeof(b),SURVEY_CONTROL,0xffff,0);b[14]=phase;b[15]=1;
    survey_send(b,sizeof(b));
}
static bool survey_range(uint8_t target,uint8_t sequence,uint16_t elapsed,SurveySample &sample,bool probe_only=false){
    uint8_t poll[18];survey_frame(poll,sizeof(poll),SURVEY_POLL,target,sequence);
    dwt_setrxaftertxdelay(100);dwt_setrxtimeout(8000);
    if(!survey_send(poll,sizeof(poll),true))return false;
    uint32_t until=millis()+15,st=0;
    while(!((st=dwt_read32bitreg(SYS_STATUS_ID))&(SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_ALL_RX_TO|SYS_STATUS_ALL_RX_ERR))){
        if((int32_t)(millis()-until)>=0){dwt_forcetrxoff();return false;}
        delayMicroseconds(20);
    }
    if(!(st&SYS_STATUS_RXFCG_BIT_MASK))return false;
    uint32_t length=(dwt_read32bitreg(RX_FINFO_ID)&RXFLEN_MASK);
    uint8_t b[64];
    if(length<FCS_LEN+22||length-FCS_LEN>sizeof(b))return false;
    dwt_readrxdata(b,length-FCS_LEN,0);
    if(read_u16_le(b+3)!=NET_PAN_ID||read_u16_le(b+5)!=ANCHOR_ID||read_u16_le(b+7)!=target||b[9]!=SURVEY_RESPONSE||b[2]!=sequence||survey_u32(b+10)!=survey_token)return false;
    // A readiness probe verifies a matching radio response only. It never
    // contributes a distance sample or bypasses the server's quality gates.
    if(probe_only){
        if(length-FCS_LEN>=24&&b[22]>=2)survey_ds_mask|=1<<(target-0xA0);
        dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_CIADONE_BIT_MASK);
        return true;
    }
    // Never use an adjusted RX timestamp/clock estimate before CIA completion.
    uint32_t cia_until=micros()+1000;
    while(!(st&(SYS_STATUS_CIADONE_BIT_MASK|SYS_STATUS_CIAERR_BIT_MASK))){
        if((int32_t)(micros()-cia_until)>=0)break;
        st=dwt_read32bitreg(SYS_STATUS_ID);
    }
    if(!(st&SYS_STATUS_CIADONE_BIT_MASK)||(st&SYS_STATUS_CIAERR_BIT_MASK)){
        Serial.printf("[SURVEY] range_reject a=%u b=%u reason=cia_not_valid status=0x%08lX\n",(unsigned)(AIDX+1),(unsigned)(target-0xA0+1),(unsigned long)st);
        dwt_forcetrxoff();return false;
    }
    uint32_t tx=dwt_readtxtimestamplo32(),rx=dwt_readrxtimestamplo32();
    int16_t clock=dwt_readclockoffset();
    dwt_rxdiag_t d={};dwt_readdiagnostics(&d);
    IpatovRaw raw={d.ipatovPower,d.ipatovF1,d.ipatovF2,d.ipatovF3,d.ipatovPeak,d.ipatovFpIndex,
        d.ipatovAccumCount,dwt_read32bitreg(0x30060),dwt_read32bitreg(DGC_CFG_ID),st,clock,
        (st&SYS_STATUS_CIADONE_BIT_MASK)!=0};
    IpatovResult q=calculate_ipatov(raw,config.rxCode,config.chan);
    uint32_t rtd=rx-tx,reply=survey_u32(b+18)-survey_u32(b+14);
    // dwt_readclockoffset already returns a sign-extended value.
    double distance=((double)rtd-(double)reply*(1.0-(double)clock/67108864.0))*.5*DWT_TIME_UNITS*SPEED_OF_LIGHT;
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_CIADONE_BIT_MASK);
    if(!isfinite(distance)||distance<=0||distance>100)return false;
    sample={(uint8_t)(AIDX+1),(uint8_t)(target-0xA0+1),sequence,elapsed,(float)distance,
            isfinite(q.difference_db)?(float)q.difference_db:0,
            isfinite(q.peak_minus_fp_samples)?(float)q.peak_minus_fp_samples:0,q.reason==nullptr};
    sample.raw_present=true;sample.poll_tx=tx;sample.response_rx=rx;
    sample.remote_poll_rx=survey_u32(b+14);sample.remote_response_tx=survey_u32(b+18);
    sample.clock_raw=clock;sample.rx_status=st;
    return true;
}
static bool survey_cia_ready(uint32_t &st){
    uint32_t until=micros()+1000;
    while(!(st&(SYS_STATUS_CIADONE_BIT_MASK|SYS_STATUS_CIAERR_BIT_MASK))){
        if((int32_t)(micros()-until)>=0){survey_trace_status(st);survey_trace_mark(ST_CIA_ERROR);return false;}
        st=dwt_read32bitreg(SYS_STATUS_ID);
    }
    bool ok=(st&SYS_STATUS_CIADONE_BIT_MASK)&&!(st&SYS_STATUS_CIAERR_BIT_MASK);
    if(!ok){survey_trace_status(st);survey_trace_mark(ST_CIA_ERROR);}return ok;
}
static IpatovResult survey_quality(uint32_t st,int16_t clock){
    dwt_rxdiag_t d={};dwt_readdiagnostics(&d);
    IpatovRaw r={d.ipatovPower,d.ipatovF1,d.ipatovF2,d.ipatovF3,d.ipatovPeak,d.ipatovFpIndex,
        d.ipatovAccumCount,dwt_read32bitreg(0x30060),dwt_read32bitreg(DGC_CFG_ID),st,clock,(st&SYS_STATUS_CIADONE_BIT_MASK)!=0};
    return calculate_ipatov(r,config.rxCode,config.chan);
}
static bool survey_receive(uint8_t *b,uint16_t &size,uint32_t &st){
    uint32_t until=millis()+20;
    while(!((st=dwt_read32bitreg(SYS_STATUS_ID))&(SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_ALL_RX_TO|SYS_STATUS_ALL_RX_ERR))){
        if((int32_t)(millis()-until)>=0){survey_trace_status(st);survey_trace_mark(ST_RX_TIMEOUT);dwt_forcetrxoff();return false;}
        delayMicroseconds(20);
    }
    survey_trace_status(st);
    if(!(st&SYS_STATUS_RXFCG_BIT_MASK)){survey_trace_mark((st&SYS_STATUS_ALL_RX_ERR)?ST_RX_ERROR:ST_RX_TIMEOUT);return false;}
    uint32_t n=dwt_read32bitreg(RX_FINFO_ID)&RXFLEN_MASK;
    if(n<FCS_LEN+14||n-FCS_LEN>64){survey_trace_mark(ST_FRAME_MISMATCH);return false;}
    size=n-FCS_LEN;dwt_readrxdata(b,size,0);survey_trace_status(st,b[9]);return true;
}
static bool survey_matches(const uint8_t *b,uint16_t n,uint8_t function,uint8_t source,uint8_t sequence){
    bool ok=n>=14&&read_u16_le(b+3)==NET_PAN_ID&&read_u16_le(b+5)==ANCHOR_ID&&read_u16_le(b+7)==source&&
        b[9]==function&&b[2]==sequence&&survey_u32(b+10)==survey_token;
    if(!ok){survey_trace_mark(ST_FRAME_MISMATCH);survey_trace_mark(ST_UNEXPECTED_RX);}return ok;
}
static bool survey_delayed(uint8_t *b,uint16_t n,uint32_t when,bool expect){
    dwt_forcetrxoff();
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_TXFRS_BIT_MASK|SYS_STATUS_RXFCG_BIT_MASK|SYS_STATUS_ALL_RX_TO|SYS_STATUS_ALL_RX_ERR|SYS_STATUS_CIADONE_BIT_MASK);
    dwt_setdelayedtrxtime(when);dwt_writetxdata(n,b,0);dwt_writetxfctrl(n,0,1);
    if(dwt_starttx(DWT_START_TX_DELAYED|(expect?DWT_RESPONSE_EXPECTED:0))!=DWT_SUCCESS){survey_trace_mark(ST_TX_ERROR);return false;}
    uint32_t until=millis()+12;
    while(!(dwt_read32bitreg(SYS_STATUS_ID)&SYS_STATUS_TXFRS_BIT_MASK)){
        if((int32_t)(millis()-until)>=0){survey_trace_mark(ST_TX_ERROR);dwt_forcetrxoff();return false;}
        delayMicroseconds(20);
    }
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_TXFRS_BIT_MASK);return true;
}
static void survey_ds_reply(){
    const uint8_t source=read_u16_le(rx_buffer+7),sequence=rx_buffer[2];
    survey_trace_select(source,ANCHOR_ID);survey_trace_mark(ST_ATTEMPT);
    uint32_t st=dwt_read32bitreg(SYS_STATUS_ID);
    if(!survey_cia_ready(st))return;
    uint64_t poll_rx=get_rx_timestamp_u64();IpatovResult poll_quality=survey_quality(st,dwt_readclockoffset());
    uint32_t when=(poll_rx+3000ULL*UUS_TO_DWT_TIME)>>8;
    uint32_t response_tx=(uint32_t)((((uint64_t)(when&0xfffffffeUL))<<8)+TX_ANT_DLY);
    uint8_t response[24];survey_frame(response,sizeof(response),SURVEY_DS_RESPONSE,source,sequence);
    survey_put32(response+14,(uint32_t)poll_rx);survey_put32(response+18,response_tx);
    dwt_setrxaftertxdelay(100);dwt_setrxtimeout(12000);
    if(!survey_delayed(response,sizeof(response),when,true))return;
    survey_trace_mark(ST_RESPONSE_TX);
    if(dwt_readtxtimestamplo32()!=response_tx){survey_trace_mark(ST_TX_TIMESTAMP_ERROR);return;}
    uint8_t final[64];uint16_t n=0;
    if(!survey_receive(final,n,st))return;
    if(n<26){survey_trace_mark(ST_FRAME_MISMATCH);return;}
    if(!survey_matches(final,n,SURVEY_DS_FINAL,source,sequence)||!survey_cia_ready(st))return;
    survey_trace_mark(ST_FINAL_RX);
    uint32_t final_rx=dwt_readrxtimestamplo32();IpatovResult final_quality=survey_quality(st,dwt_readclockoffset());
    float gap=isfinite(poll_quality.difference_db)&&isfinite(final_quality.difference_db)?fmax(poll_quality.difference_db,final_quality.difference_db):0;
    float path=fabs(poll_quality.peak_minus_fp_samples)>fabs(final_quality.peak_minus_fp_samples)?poll_quality.peak_minus_fp_samples:final_quality.peak_minus_fp_samples;
    if(!isfinite(path))path=0;
    uint8_t result[37];survey_frame(result,sizeof(result),SURVEY_DS_RESULT,source,sequence);
    survey_put32(result+14,(uint32_t)poll_rx);survey_put32(result+18,response_tx);survey_put32(result+22,final_rx);
    memcpy(result+26,&gap,4);memcpy(result+30,&path,4);result[34]=poll_quality.reason==nullptr&&final_quality.reason==nullptr;
    if(survey_send(result,sizeof(result)))survey_trace_mark(ST_RESULT_TX);else survey_trace_mark(ST_TX_ERROR);
}
static bool survey_ds_range(uint8_t target,uint8_t sequence,uint16_t elapsed,SurveySample &sample){
    survey_trace_select(ANCHOR_ID,target);survey_trace_mark(ST_ATTEMPT);
    uint8_t poll[18];survey_frame(poll,sizeof(poll),SURVEY_DS_POLL,target,sequence);
    dwt_setrxaftertxdelay(100);dwt_setrxtimeout(12000);
    if(!survey_send(poll,sizeof(poll),true)){survey_trace_mark(ST_TX_ERROR);return false;}
    survey_trace_mark(ST_POLL_TX);
    uint8_t b[64];uint16_t n=0;uint32_t st=0;
    if(!survey_receive(b,n,st))return false;
    if(n<22){survey_trace_mark(ST_FRAME_MISMATCH);return false;}
    if(!survey_matches(b,n,SURVEY_DS_RESPONSE,target,sequence)||!survey_cia_ready(st))return false;
    survey_trace_mark(ST_RESPONSE_RX);
    uint32_t poll_tx=dwt_readtxtimestamplo32();uint64_t response_rx=get_rx_timestamp_u64();
    int16_t clock=dwt_readclockoffset();uint32_t response_status=st;IpatovResult quality=survey_quality(st,clock);
    uint32_t when=(response_rx+3000ULL*UUS_TO_DWT_TIME)>>8;
    uint32_t final_tx=(uint32_t)((((uint64_t)(when&0xfffffffeUL))<<8)+TX_ANT_DLY);
    uint8_t final[28];survey_frame(final,sizeof(final),SURVEY_DS_FINAL,target,sequence);
    survey_put32(final+14,poll_tx);survey_put32(final+18,(uint32_t)response_rx);survey_put32(final+22,final_tx);
    dwt_setrxaftertxdelay(100);dwt_setrxtimeout(12000);
    if(!survey_delayed(final,sizeof(final),when,true))return false;
    survey_trace_mark(ST_FINAL_TX);
    if(dwt_readtxtimestamplo32()!=final_tx){survey_trace_mark(ST_TX_TIMESTAMP_ERROR);return false;}
    if(!survey_receive(b,n,st))return false;
    if(n<35){survey_trace_mark(ST_FRAME_MISMATCH);return false;}
    if(!survey_matches(b,n,SURVEY_DS_RESULT,target,sequence))return false;
    survey_trace_mark(ST_RESULT_RX);
    uint32_t remote_rx=survey_u32(b+14),remote_tx=survey_u32(b+18),remote_final_rx=survey_u32(b+22);
    double ra=(uint32_t)((uint32_t)response_rx-poll_tx),rb=(uint32_t)(remote_final_rx-remote_tx);
    double da=(uint32_t)(final_tx-(uint32_t)response_rx),db=(uint32_t)(remote_tx-remote_rx);
    if(ra<=0||rb<=0||da<=0||db<=0||ra>=0x80000000UL||rb>=0x80000000UL||da>=0x80000000UL||db>=0x80000000UL){survey_trace_mark(ST_INTERVAL_ERROR);return false;}
    double distance=(ra*rb-da*db)/(ra+rb+da+db)*DWT_TIME_UNITS*SPEED_OF_LIGHT;
    survey_trace_distance(distance);
    if(!isfinite(distance)||distance<=0||distance>100){survey_trace_mark(ST_DISTANCE_ERROR);return false;}
    survey_trace_mark(ST_DISTANCE_OK);
    float remote_gap,remote_path;memcpy(&remote_gap,b+26,4);memcpy(&remote_path,b+30,4);
    sample={};sample.a=AIDX+1;sample.b=target-0xA0+1;sample.sequence=sequence;sample.elapsed=elapsed;sample.distance=distance;
    sample.gap=isfinite(quality.difference_db)&&isfinite(remote_gap)?fmax(quality.difference_db,remote_gap):0;
    sample.path=fabs(quality.peak_minus_fp_samples)>fabs(remote_path)?quality.peak_minus_fp_samples:remote_path;
    if(!isfinite(sample.path))sample.path=0;
    sample.valid=quality.reason==nullptr&&b[34]&&isfinite(remote_gap)&&isfinite(remote_path);
    sample.raw_present=true;sample.ds=true;sample.poll_tx=poll_tx;sample.response_rx=(uint32_t)response_rx;
    sample.remote_poll_rx=remote_rx;sample.remote_response_tx=remote_tx;sample.final_tx=final_tx;sample.remote_final_rx=remote_final_rx;
    sample.clock_raw=clock;sample.rx_status=response_status;return true;
}
static void survey_reply(){
    uint32_t delayed=(last_rx_ts+3000ULL*UUS_TO_DWT_TIME)>>8;
    uint64_t tx=(((uint64_t)(delayed&0xfffffffeUL))<<8)+TX_ANT_DLY;
    uint8_t b[26];survey_frame(b,sizeof(b),SURVEY_RESPONSE,read_u16_le(rx_buffer+7),rx_buffer[2]);
    resp_msg_set_ts(b+14,last_rx_ts);resp_msg_set_ts(b+18,tx);
    b[22]=2; // DS-TWR capability; ignored by existing SS-only coordinators.
    dwt_setdelayedtrxtime(delayed);dwt_writetxdata(sizeof(b),b,0);dwt_writetxfctrl(sizeof(b),0,1);
    if(dwt_starttx(DWT_START_TX_DELAYED)==DWT_SUCCESS){
        uint32_t until=millis()+15;
        while(!(dwt_read32bitreg(SYS_STATUS_ID)&SYS_STATUS_TXFRS_BIT_MASK)){
            if((int32_t)(millis()-until)>=0){dwt_forcetrxoff();break;}
        }
    }
    dwt_write32bitreg(SYS_STATUS_ID,SYS_STATUS_TXFRS_BIT_MASK);
}
// Collect only after the 10s distance window; missing reports stay explicit.
// Wire payload: header14, pair1, version1, counters24, status4, function1, distance4.
static void survey_trace_respond(uint8_t pair,uint32_t token,uint8_t sequence){
    if(pair>=6||token!=survey_trace_token)return;
    const auto &t=survey_traces[pair];uint8_t b[51];
    survey_frame(b,sizeof(b),SURVEY_TRACE_RESPONSE,MASTER_ANCHOR_ID,sequence);
    survey_put32(b+10,token);b[14]=pair;b[15]=1;memcpy(b+16,t.counts,ST_COUNT);
    survey_put32(b+40,t.last_status);b[44]=t.last_function;memcpy(b+45,&t.last_distance,4);
    delay(2);survey_send(b,sizeof(b));
}
#if ANCHOR_ID == MASTER_ANCHOR_ID
static void survey_trace_collect(){
    survey_trace_pair=255;survey_result.trace_count=0;
    for(uint8_t anchor=0xA0;anchor<=0xA3;++anchor)for(uint8_t pair=0;pair<6;++pair){
        if(anchor!=ANCHOR_ID&&survey_pairs[pair][0]!=anchor&&survey_pairs[pair][1]!=anchor)continue;
        auto &t=survey_result.traces[survey_result.trace_count++];memset(&t,0,sizeof(t));
        t.anchor=anchor-0xA0+1;t.a=survey_pairs[pair][0]-0xA0+1;t.b=survey_pairs[pair][1]-0xA0+1;t.last_distance=NAN;
        if(anchor==ANCHOR_ID){t=survey_traces[pair];continue;}
        for(uint8_t attempt=0;attempt<2&&!t.received;++attempt){
            uint8_t request[18];uint8_t seq=pair+attempt*6;
            survey_frame(request,sizeof(request),SURVEY_TRACE_POLL,anchor,seq);request[14]=pair;
            dwt_setrxaftertxdelay(100);dwt_setrxtimeout(8000);
            if(!survey_send(request,sizeof(request),true))continue;
            uint8_t b[64];uint16_t n=0;uint32_t st=0;
            if(!survey_receive(b,n,st)||n<49||b[14]!=pair||b[15]!=1||
               !survey_matches(b,n,SURVEY_TRACE_RESPONSE,anchor,seq))continue;
            memcpy(t.counts,b+16,ST_COUNT);t.last_status=survey_u32(b+40);t.last_function=b[44];
            memcpy(&t.last_distance,b+45,4);t.received=true;
        }
    }
    for(unsigned i=0;i<survey_result.trace_count;++i){const auto &t=survey_result.traces[i];
        Serial.printf("[SURVEY_TRACE] anchor=%u pair=%u-%u received=%u",t.anchor,t.a,t.b,t.received);
        for(unsigned j=0;j<ST_COUNT;++j)if(t.counts[j])Serial.printf(" %s=%u",SURVEY_STAGE_NAMES[j],t.counts[j]);
        Serial.printf(" last_status=0x%08lX last_function=0x%02X last_distance=%.5f\n",(unsigned long)t.last_status,t.last_function,t.last_distance);
    }
}
#endif
static void survey_finish(bool ok,const char *error){
#if ANCHOR_ID == MASTER_ANCHOR_ID
    // Post-window trace collection and UART output do not extend sample time.
    uint32_t duration=(uint32_t)(millis()-survey_measure_at);
    if(survey_token){for(int i=0;i<3;++i){survey_control(2);delay(3);}}
    if(survey_measuring)survey_trace_collect();
    survey_result.prepared=false;survey_result.completed=ok;
    survey_result.duration=survey_measuring?(duration>11000?11000:duration):0;
    strlcpy(survey_result.error,error,sizeof(survey_result.error));
    xQueueSend(survey_results,&survey_result,0);
#endif
    survey_token=0;survey_measuring=false;survey_prepared=false;
    Serial.printf("[SURVEY] finished ok=%d reason=%s ready_mask=0x%02X samples=%u\n",ok,error,survey_mask,survey_result.count);
}
static bool survey_handle(uint16_t length){
    uint8_t func=rx_buffer[9];
    if(func<SURVEY_CONTROL||func>SURVEY_TRACE_RESPONSE)return false;
    if(length<14)return true;
    uint32_t token=survey_u32(rx_buffer+10);
    uint16_t src=read_u16_le(rx_buffer+7),dst=read_u16_le(rx_buffer+5);
    if(func==SURVEY_TRACE_POLL&&src==MASTER_ANCHOR_ID&&dst==ANCHOR_ID&&length>=15){
        survey_trace_respond(rx_buffer[14],token,rx_buffer[2]);return true;
    }
    if(func==SURVEY_CONTROL&&src==MASTER_ANCHOR_ID&&length>=16&&rx_buffer[15]==1){
#if ANCHOR_ID != MASTER_ANCHOR_ID
        uint8_t phase=rx_buffer[14];
        if(phase==2&&token==survey_token){survey_token=0;return true;}
        if(phase==0||phase==1){
            if(token!=survey_token){survey_created=millis();if(token!=survey_trace_token)survey_trace_reset(token);}
            survey_token=token;survey_deadline=millis()+12000;
            if(phase==0){
                delay(3+AIDX*3);uint8_t b[20];survey_frame(b,sizeof(b),SURVEY_READY,MASTER_ANCHOR_ID,0);b[14]=1;survey_send(b,sizeof(b));
            }
        }
#endif
        return true;
    }
    if(!survey_token||token!=survey_token||dst!=ANCHOR_ID)return true;
#if ANCHOR_ID == MASTER_ANCHOR_ID
    if(func==SURVEY_READY&&length>=15&&rx_buffer[14]==1&&src>=0xA1&&src<=0xA3){
        uint8_t previous=survey_mask;survey_mask|=1<<(src-0xA0);
        if(previous!=survey_mask)Serial.printf("[SURVEY] ready anchor=%u mask=0x%02X elapsed_ms=%lu\n",(unsigned)(src-0xA0+1),survey_mask,(unsigned long)(millis()-survey_created));
    }
    if(func==SURVEY_RESULT&&length>=30&&survey_measuring&&survey_result.count<SURVEY_MAX_SAMPLES&&src>=0xA1&&src<=0xA2){
        uint8_t expected=(uint8_t)(survey_sequence-1);
        if(rx_buffer[2]!=expected||src!=survey_pairs[expected%6][0]||rx_buffer[14]!=survey_pairs[expected%6][1])return true;
        survey_trace_select(src,rx_buffer[14]);survey_trace_mark(ST_RELAY_RX);survey_trace_pair=255;
        SurveySample sample={};sample.a=src-0xA0+1;sample.b=rx_buffer[14]-0xA0+1;
        sample.sequence=rx_buffer[2];sample.elapsed=read_u16_le(rx_buffer+15);
        memcpy(&sample.distance,rx_buffer+17,4);memcpy(&sample.gap,rx_buffer+21,4);memcpy(&sample.path,rx_buffer+25,4);
        sample.valid=rx_buffer[29]!=0;
        if(length>=61&&(rx_buffer[60]==1||rx_buffer[60]==2)){
            sample.raw_present=true;sample.ds=rx_buffer[60]==2;
            sample.poll_tx=survey_u32(rx_buffer+30);sample.response_rx=survey_u32(rx_buffer+34);
            sample.remote_poll_rx=survey_u32(rx_buffer+38);sample.remote_response_tx=survey_u32(rx_buffer+42);
            sample.final_tx=survey_u32(rx_buffer+46);sample.remote_final_rx=survey_u32(rx_buffer+50);
            memcpy(&sample.clock_raw,rx_buffer+54,2);sample.rx_status=survey_u32(rx_buffer+56);
        }
        if(sample.b>sample.a&&sample.b<=4&&sample.elapsed<10000&&isfinite(sample.distance)&&sample.distance>0&&sample.distance<=100&&isfinite(sample.gap)&&isfinite(sample.path))
            survey_result.samples[survey_result.count++]=sample;
    }
#endif
    if(func==SURVEY_SLOT&&src==MASTER_ANCHOR_ID&&length>=17){
        uint8_t target=rx_buffer[14];
        if(target>ANCHOR_ID&&target<=0xA3){
            survey_trace_select(ANCHOR_ID,target);survey_trace_mark(ST_SLOT_RX);
            SurveySample s;delay(2);
            bool ds=length>=18&&rx_buffer[17]==2;
            if(!ds)survey_trace_mark(ST_SS_ATTEMPT);
            if(ds?survey_ds_range(target,rx_buffer[2],read_u16_le(rx_buffer+15),s):survey_range(target,rx_buffer[2],read_u16_le(rx_buffer+15),s)){
                uint8_t b[63];survey_frame(b,sizeof(b),SURVEY_RESULT,MASTER_ANCHOR_ID,s.sequence);b[14]=target;write_u16_le(b+15,s.elapsed);
                memcpy(b+17,&s.distance,4);memcpy(b+21,&s.gap,4);memcpy(b+25,&s.path,4);b[29]=s.valid;
                survey_put32(b+30,s.poll_tx);survey_put32(b+34,s.response_rx);
                survey_put32(b+38,s.remote_poll_rx);survey_put32(b+42,s.remote_response_tx);
                survey_put32(b+46,s.final_tx);survey_put32(b+50,s.remote_final_rx);
                memcpy(b+54,&s.clock_raw,2);survey_put32(b+56,s.rx_status);b[60]=s.ds?2:1;
                delay(2); // Let the coordinator rearm RX after hearing the peer result.
                if(survey_send(b,sizeof(b)))survey_trace_mark(ST_RELAY_TX);else survey_trace_mark(ST_RELAY_ERROR);
            }
            survey_trace_pair=255;
        }
    }else if(func==SURVEY_POLL&&src>=0xA0&&src<ANCHOR_ID)survey_reply();
    else if(func==SURVEY_DS_POLL&&src>=0xA0&&src<ANCHOR_ID){survey_ds_reply();survey_trace_pair=255;}
    return true;
}

#if ANCHOR_ID == MASTER_ANCHOR_ID
static bool survey_http(const String &path,const String &body,String &response){
    HTTPClient http;String base=HANMIR_SERVER_URL;int cut=base.indexOf("/api/");if(cut<0)return false;base=base.substring(0,cut);
    http.setConnectTimeout(1200);http.setTimeout(1500);http.begin(base+"/api/anchor-survey"+path);
    http.addHeader("Authorization",String("Bearer ")+HANMIR_SURVEY_TOKEN);http.addHeader("Content-Type","application/json");
    int code=http.POST(body);response=code>0?http.getString():"";http.end();return code>=200&&code<300;
}
static void survey_network(void*){
    uint32_t polled=0;char last_session[33]={};bool active=false;
    // Keep the enlarged diagnostic report off this task's stack.
    static SurveyResult report;
    hanmir_wifi_begin();
    for(;;){
        hanmir_wifi_maintain();
        if(xQueueReceive(survey_results,&report,0)==pdTRUE){
            DynamicJsonDocument doc(48000);doc["nonce"]=report.context.nonce;String response,body;
            if(report.prepared){
                doc["ready_mask"]=report.ready;serializeJson(doc,body);
                SurveyCommand cmd=report.context;cmd.kind=survey_http(String("/device/")+cmd.session+"/begin",body,response)?2:3;
                xQueueSend(survey_commands,&cmd,0);
            }else{
                doc["completed"]=report.completed;doc["duration_ms"]=report.duration;doc["error"]=report.error;
                JsonArray samples=doc.createNestedArray("samples");
                for(int i=0;i<report.count;++i){auto &s=report.samples[i];JsonObject o=samples.createNestedObject();
                    o["a"]=s.a;o["b"]=s.b;o["sequence"]=s.sequence;o["elapsed_ms"]=s.elapsed;o["distance_m"]=s.distance;
                    o["diagnostic_valid"]=s.valid;o["gap_db"]=s.gap;o["path_samples"]=s.path;
                    if(s.raw_present){
                        o["poll_tx_dtu_low32"]=s.poll_tx;o["response_rx_dtu_low32"]=s.response_rx;
                        o["remote_poll_rx_dtu_low32"]=s.remote_poll_rx;o["remote_response_tx_dtu_low32"]=s.remote_response_tx;
                        o["clock_offset_raw"]=s.clock_raw;o["sys_status"]=s.rx_status;
                        o["ranging_method"]=s.ds?"ds-twr":"ss-twr";
                        if(s.ds){o["final_tx_dtu_low32"]=s.final_tx;o["remote_final_rx_dtu_low32"]=s.remote_final_rx;}
                    }}
                JsonArray traces=doc.createNestedArray("stage_diagnostics");
                for(unsigned i=0;i<report.trace_count;++i){const auto &t=report.traces[i];auto o=traces.createNestedObject();
                    o["anchor"]=t.anchor;o["a"]=t.a;o["b"]=t.b;o["received"]=t.received;o["version"]=1;
                    JsonArray counts=o.createNestedArray("counts");for(unsigned j=0;j<ST_COUNT;++j)counts.add(t.counts[j]);
                    o["last_status"]=t.last_status;o["last_function"]=t.last_function;
                    if(isfinite(t.last_distance))o["last_distance"]=t.last_distance;else o["last_distance"]=nullptr;
                }
                if(doc.overflowed()){
                    doc.clear();doc["nonce"]=report.context.nonce;doc["completed"]=false;
                    doc["duration_ms"]=report.duration;doc["error"]="diagnostic_json_overflow";doc.createNestedArray("samples");
                }
                serializeJson(doc,body);
                bool sent=false;for(int i=0;i<3&&!sent;++i){sent=survey_http(String("/device/")+report.context.session+"/complete",body,response);if(!sent)vTaskDelay(pdMS_TO_TICKS(300));}
                Serial.printf("[SURVEY] result upload=%d samples=%u json_bytes=%u json_mem=%u heap_free=%u heap_min=%u stack_min=%u\n",sent,report.count,(unsigned)body.length(),(unsigned)doc.memoryUsage(),ESP.getFreeHeap(),ESP.getMinFreeHeap(),(unsigned)uxTaskGetStackHighWaterMark(nullptr));active=false;
            }
        }
        if(millis()-polled>1000){
            polled=millis();
            if(WiFi.status()!=WL_CONNECTED){vTaskDelay(pdMS_TO_TICKS(100));continue;}
            String response;
            String heartbeat=String("{\"protocol\":1,\"firmware\":\"anchor-survey-v3-trace\",\"busy\":")+(active?"true}":"false}");
            heartbeat.remove(heartbeat.length()-1);
            heartbeat+=String(",\"heap_free_bytes\":")+ESP.getFreeHeap()+",\"heap_min_bytes\":"+ESP.getMinFreeHeap()+",\"stack_high_watermark_raw\":"+(unsigned)uxTaskGetStackHighWaterMark(nullptr)+"}";
            if(survey_http("/device/poll",heartbeat,response)){
                StaticJsonDocument<512> doc;
                if(!deserializeJson(doc,response)){
                    const char *id=doc["session_id"]|"";const char *nonce=doc["nonce"]|"";
                    if(String(doc["command"]|"")=="survey"&&strlen(id)==32&&strlen(nonce)==32){
                        if(strcmp(id,last_session)){SurveyCommand c={};c.kind=1;strlcpy(c.session,id,33);strlcpy(c.nonce,nonce,33);
                            if(xQueueSend(survey_commands,&c,0)==pdTRUE){strlcpy(last_session,id,33);active=true;}}
                    }else if(active){SurveyCommand c={};c.kind=3;xQueueSend(survey_commands,&c,0);active=false;}
                }
            }
        }
        vTaskDelay(pdMS_TO_TICKS(20));
    }
}
#endif
static void survey_setup(){
    dwt_configciadiag(DW_CIA_DIAG_LOG_ALL);
#if ANCHOR_ID == MASTER_ANCHOR_ID
    survey_commands=xQueueCreate(4,sizeof(SurveyCommand));survey_results=xQueueCreate(2,sizeof(SurveyResult));
    if(survey_commands&&survey_results&&strlen(HANMIR_SURVEY_TOKEN)>0)
        xTaskCreatePinnedToCore(survey_network,"anchor_survey_net",16384,nullptr,1,nullptr,0);
#endif
}
static void survey_tick(){
#if ANCHOR_ID == MASTER_ANCHOR_ID
    if(!survey_commands||!survey_results)return;
    SurveyCommand cmd;
    if(xQueueReceive(survey_commands,&cmd,0)==pdTRUE){
        if(cmd.kind==1&&!survey_active()){
            memset(&survey_result,0,sizeof(survey_result));survey_result.context=cmd;
            char hex[9];memcpy(hex,cmd.nonce,8);hex[8]=0;survey_token=strtoul(hex,nullptr,16);if(!survey_token)survey_token=1;
            survey_trace_reset(survey_token);
            survey_created=millis();survey_mask=1;survey_ds_mask=1;survey_ds_mode=false;survey_prepared=false;survey_measuring=false;survey_last_slot=0;
            Serial.println("[SURVEY] preparing expected_mask=0x0F");
        }else if(cmd.kind==2&&survey_active()){
            survey_measuring=true;survey_measure_at=millis();survey_last_slot=0;survey_sequence=0;
            for(int i=0;i<3;++i){survey_control(1);delay(3);}
        }else if(cmd.kind==3&&survey_active())survey_finish(false,"cancelled");
    }
    if(!survey_active())return;
    uint32_t now=millis();
    if(!survey_measuring){
        if(now-survey_created>8000){survey_finish(false,"anchor_ready_timeout");return;}
        if(!survey_prepared&&now-survey_last_slot>=200){
            // Legacy peers already accept phase 1 and respond to directed
            // SURVEY_POLL. Wake them without soliciting simultaneous READYs.
            survey_control(1);survey_last_slot=now;
            if(now-survey_created>=1500){
                delay(3);
                for(uint8_t target=0xA1;target<=0xA3;++target){
                    uint8_t bit=1<<(target-0xA0);
                    if(survey_mask&bit)continue;
                    SurveySample unused={};
                    if(survey_range(target,target-0xA0,0,unused,true)){
                        survey_mask|=bit;
                        Serial.printf("[SURVEY] directed_ready anchor=%u mask=0x%02X elapsed_ms=%lu\n",(unsigned)(target-0xA0+1),survey_mask,(unsigned long)(millis()-survey_created));
                    }
                    delay(2);
                }
            }
        }
        // Existing tags stop ranging after 900ms without ordinary beacons.
        if(!survey_prepared&&survey_mask==15&&now-survey_created>=1500){
            survey_ds_mode=survey_ds_mask==15;
            Serial.printf("[SURVEY] ranging_method=%s ds_capable_mask=0x%02X\n",survey_ds_mode?"ds-twr":"ss-twr",survey_ds_mask);
            survey_result.prepared=true;survey_result.ready=survey_mask;
            if(xQueueSend(survey_results,&survey_result,0)==pdTRUE)survey_prepared=true;
        }
    }else{
        if(now-survey_measure_at>=10000){survey_finish(true,"");return;}
        if(now-survey_last_slot>=100){
            auto &pair=survey_pairs[survey_sequence%6];uint16_t elapsed=now-survey_measure_at;uint8_t sequence=survey_sequence++;
            survey_last_slot=now;
            if(pair[0]==ANCHOR_ID){SurveySample sample;
                bool ok=survey_ds_mode?survey_ds_range(pair[1],sequence,elapsed,sample):survey_range(pair[1],sequence,elapsed,sample);
                if(ok&&survey_result.count<SURVEY_MAX_SAMPLES)survey_result.samples[survey_result.count++]=sample;
            }else{
                survey_trace_select(pair[0],pair[1]);
                uint8_t b[20];survey_frame(b,sizeof(b),SURVEY_SLOT,pair[0],sequence);b[14]=pair[1];write_u16_le(b+15,elapsed);b[17]=survey_ds_mode?2:1;
                if(survey_send(b,sizeof(b)))survey_trace_mark(ST_SLOT_TX);else survey_trace_mark(ST_TX_ERROR);
                survey_trace_pair=255;
            }
        }
    }
#else
    if(survey_active()&&((int32_t)(millis()-survey_deadline)>=0||millis()-survey_created>20000))survey_token=0;
#endif
}
