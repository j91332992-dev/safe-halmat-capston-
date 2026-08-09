.section .rodata.acknowledgement_wav,"a",@progbits
.global acknowledgement_wav_start
.global acknowledgement_wav_end
.align 4
acknowledgement_wav_start:
  .incbin "src/acknowledgement.wav"
acknowledgement_wav_end:
