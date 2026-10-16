idf_component_register(SRCS "model_benchmark.cc" INCLUDE_DIRS "."
    EMBED_FILES "tutus_pilot.tflite" REQUIRES esp_timer esp-tflite-micro tutus_frontend)
