param([Parameter(Mandatory=$true)][string]$Config)
$env:TF_NUM_INTRAOP_THREADS='2'
$env:TF_NUM_INTEROP_THREADS='1'
$env:OMP_NUM_THREADS='2'
$env:PYTHONIOENCODING='utf-8'
& C:/dev/hanmir-wake-training/venv/Scripts/python.exe -m microwakeword.model_train_eval --training_config=$Config --train 1 --restore_checkpoint 0 --test_tf_nonstreaming 0 --test_tflite_nonstreaming 0 --test_tflite_nonstreaming_quantized 0 --test_tflite_streaming 0 --test_tflite_streaming_quantized 1 --use_weights best_weights mixednet --pointwise_filters '16,16,16,16' --repeat_in_block '1,1,1,1' --mixconv_kernel_sizes '[5],[7,11],[9,15],[23]' --residual_connection '0,0,0,0' --first_conv_filters 16 --first_conv_kernel_size 5 --stride 3
exit $LASTEXITCODE
