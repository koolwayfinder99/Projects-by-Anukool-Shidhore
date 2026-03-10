###############################################################################
# Makefile for STM32F4 Mobile Robot Firmware
# 
# This Makefile automates the build process for the STM32F4-based differential
# drive mobile robot. It uses the ARM GCC toolchain with hardware floating-point
# support for the Cortex-M4 processor.
#
# Targets:
#   make all    - Build the firmware
#   make clean  - Remove all build artifacts
#   make flash  - Program the STM32 device (requires st-flash or similar)
#
###############################################################################

# ============================================================================
# Compiler and Tools Configuration
# ============================================================================

# ARM GCC Toolchain
ARM_TOOLCHAIN := arm-none-eabi
CC := $(ARM_TOOLCHAIN)-gcc
AS := $(ARM_TOOLCHAIN)-as
LD := $(ARM_TOOLCHAIN)-ld
OBJCOPY := $(ARM_TOOLCHAIN)-objcopy
OBJDUMP := $(ARM_TOOLCHAIN)-objdump
AR := $(ARM_TOOLCHAIN)-ar
SIZE := $(ARM_TOOLCHAIN)-size

# Optional: st-link utilities for programming
STFLASH := st-flash

# ============================================================================
# Project Structure
# ============================================================================

# Directory organization
PROJECT_NAME := stm32_mobile_robot
CORE_DIR := Core
INC_DIR := $(CORE_DIR)/Inc
SRC_DIR := $(CORE_DIR)/Src
BUILD_DIR := build
BIN_DIR := bin

# Firmware output files
ELF_FILE := $(BIN_DIR)/$(PROJECT_NAME).elf
HEX_FILE := $(BIN_DIR)/$(PROJECT_NAME).hex
BIN_FILE := $(BIN_DIR)/$(PROJECT_NAME).bin
MAP_FILE := $(BIN_DIR)/$(PROJECT_NAME).map

# ============================================================================
# Source Files
# ============================================================================

# Main application source files
SOURCES = \
    $(SRC_DIR)/main.c

# HAL Driver sources (paths would be updated based on actual HAL location)
# HAL_SOURCES = \
#     Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal.c \
#     Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_tim.c \
#     Drivers/STM32F4xx_HAL_Driver/Src/stm32f4xx_hal_gpio.c

# Startup file (system initialization)
# STARTUP_ASM := Drivers/CMSIS/Device/ST/STM32F4xx/Source/Templates/gcc/startup_stm32f407xx.s

# CMSIS system initialization
# SYSTEM_C := Drivers/CMSIS/Device/ST/STM32F4xx/Source/Templates/system_stm32f4xx.c

# Combine all sources
# ALL_SOURCES = $(SOURCES) $(HAL_SOURCES) $(SYSTEM_C)

# Object files
OBJECTS = $(addprefix $(BUILD_DIR)/, $(notdir $(SOURCES:.c=.o)))

# ============================================================================
# Compiler and Linker Flags
# ============================================================================

# Target Architecture Configuration
CPU := cortex-m4
FPU := fpv4-sp-d16
ABI := eabi

# Compiler flags for ARM Cortex-M4 with floating-point support
CFLAGS = \
    -mcpu=$(CPU) \
    -mthumb \
    -mfpu=$(FPU) \
    -mfloat-abi=hard \
    -Wall \
    -Wextra \
    -O2 \
    -ffunction-sections \
    -fdata-sections \
    -DSTM32F407xx \
    -DUSE_HAL_DRIVER

# Assembler flags
ASFLAGS = \
    -mcpu=$(CPU) \
    -mthumb \
    -mfpu=$(FPU) \
    -mfloat-abi=hard \
    -x assembler-with-cpp

# Include paths
INCLUDES = \
    -I$(INC_DIR) \
    -IDrivers/STM32F4xx_HAL_Driver/Inc \
    -IDrivers/CMSIS/Include \
    -IDrivers/CMSIS/Device/ST/STM32F4xx/Include

# Linker script
LINKER_SCRIPT := STM32F407VGTx_FLASH.ld

# Linker flags
LDFLAGS = \
    -mcpu=$(CPU) \
    -mthumb \
    -mfpu=$(FPU) \
    -mfloat-abi=hard \
    --specs=nano.specs \
    --specs=nosys.specs \
    -Wl,--gc-sections \
    -Wl,--print-memory-usage \
    -Wl,-Map=$(MAP_FILE) \
    -T$(LINKER_SCRIPT)

# ============================================================================
# Build Rules
# ============================================================================

# Default target
all: $(BIN_DIR) $(BUILD_DIR) $(ELF_FILE) $(HEX_FILE) $(BIN_FILE)
	@echo "Build complete!"
	@$(SIZE) $(ELF_FILE)

# Create necessary directories
$(BIN_DIR):
	@mkdir -p $@

$(BUILD_DIR):
	@mkdir -p $@

# Link the executable
$(ELF_FILE): $(OBJECTS)
	@echo "Linking $(PROJECT_NAME)..."
	$(LD) $(LDFLAGS) $(OBJECTS) -o $@
	@echo "Linking complete!"

# Compile C source files
$(BUILD_DIR)/%.o: $(SRC_DIR)/%.c | $(BUILD_DIR)
	@echo "Compiling $(notdir $<)..."
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# Generate hex file
$(HEX_FILE): $(ELF_FILE)
	@echo "Generating HEX file..."
	$(OBJCOPY) -O ihex $< $@

# Generate binary file
$(BIN_FILE): $(ELF_FILE)
	@echo "Generating BIN file..."
	$(OBJCOPY) -O binary $< $@

# ============================================================================
# Utility Targets
# ============================================================================

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(BUILD_DIR) $(BIN_DIR)
	@echo "Clean complete!"

# Flash firmware to STM32 (requires st-link tools)
flash: $(BIN_FILE)
	@echo "Flashing firmware to STM32..."
	$(STFLASH) write $< 0x08000000
	@echo "Flash complete!"

# Display disassembly
disassemble: $(ELF_FILE)
	$(OBJDUMP) -D $< > $(BIN_DIR)/$(PROJECT_NAME).dis
	@echo "Disassembly written to $(BIN_DIR)/$(PROJECT_NAME).dis"

# Display size information
size: $(ELF_FILE)
	$(SIZE) $<

# Help target
help:
	@echo "STM32 Mobile Robot Firmware Build System"
	@echo "=========================================="
	@echo "Available targets:"
	@echo "  make all       - Build the firmware (default)"
	@echo "  make clean     - Remove all build artifacts"
	@echo "  make flash     - Program firmware to device"
	@echo "  make disassemble - Generate disassembly listing"
	@echo "  make size      - Display binary size information"
	@echo "  make help      - Display this help message"
	@echo ""
	@echo "Configuration:"
	@echo "  Compiler: $(CC)"
	@echo "  Target:   STM32F4 Cortex-M4 with FPU"
	@echo "  Linker:   $(LINKER_SCRIPT)"

# Phony targets (not actual files)
.PHONY: all clean flash disassemble size help

# ============================================================================
# Debug Information
# ============================================================================

print-%:
	@echo $* = $($*)

# Enable verbose output during build
VERBOSE ?= 0

ifeq ($(VERBOSE), 1)
    MAKEFLAGS =
else
    MAKEFLAGS += --no-print-directory
endif
