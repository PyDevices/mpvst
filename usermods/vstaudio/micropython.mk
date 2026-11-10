VSTAUDIO_MOD_DIR := $(USERMOD_DIR)
VSTAUDIO_SOURCE_DIR := $(realpath $(VSTAUDIO_MOD_DIR))
VSTAUDIO_ROOT := $(abspath $(VSTAUDIO_SOURCE_DIR)/../..)

CFLAGS_USERMOD += \
    -Wno-error=double-promotion \
    -I$(VSTAUDIO_MOD_DIR)/src \
    -I$(VSTAUDIO_ROOT)/src/protocol/include

SRC_USERMOD_C += $(VSTAUDIO_MOD_DIR)/src/modvstaudio.c

# Which vstaudio this engine was built from: vstaudio.__revision__.
VSTAUDIO_REVISION := $(shell git -C $(VSTAUDIO_MOD_DIR) describe --always --dirty --abbrev=7 2>/dev/null || echo unknown)
CFLAGS_USERMOD += -DVSTAUDIO_REVISION='"$(VSTAUDIO_REVISION)"'
