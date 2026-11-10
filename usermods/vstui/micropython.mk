VSTUI_MOD_DIR := $(USERMOD_DIR)
VSTUI_SOURCE_DIR := $(realpath $(VSTUI_MOD_DIR))
VSTUI_ROOT := $(abspath $(VSTUI_SOURCE_DIR)/../..)

CFLAGS_USERMOD += \
    -I$(VSTUI_MOD_DIR)/src \
    -I$(VSTUI_ROOT)/src/protocol/include

SRC_USERMOD_C += $(VSTUI_MOD_DIR)/src/modvstui.c

# Which vstui this engine was built from: vstui.__revision__.
VSTUI_REVISION := $(shell git -C $(VSTUI_MOD_DIR) describe --always --dirty --abbrev=7 2>/dev/null || echo unknown)
CFLAGS_USERMOD += -DVSTUI_REVISION='"$(VSTUI_REVISION)"'
