/**
 * @file main.h
 * @brief Main header file for STM32F4 Firmware
 * @author Robotics Team
 * @date 2026
 *
 * This header file contains the main definitions, includes, and function
 * prototypes for the STM32F4 microcontroller firmware running on the
 * differential drive mobile robot.
 */

#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* ============================================================================
 * Standard Library Includes
 * ========================================================================== */
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

/* ============================================================================
 * HAL Driver Includes
 * ========================================================================== */
#include "stm32f4xx_hal.h"

/* ============================================================================
 * Macros and Constants
 * ========================================================================== */

/** @defgroup Status_LED_Configuration
 * @{
 */
#define LED_GPIO_PORT               GPIOA
#define LED_GPIO_PIN                GPIO_PIN_5
/** @} */

/** @defgroup Motor_PWM_Configuration
 * @{
 */
#define MOTOR_TIMER                 TIM1
#define MOTOR_LEFT_CHANNEL          TIM_CHANNEL_1
#define MOTOR_RIGHT_CHANNEL         TIM_CHANNEL_2
#define MOTOR_PWM_FREQUENCY         1000U           /* Hz */
#define MOTOR_PWM_MAX_PULSE         1000U
#define MOTOR_PWM_MIN_PULSE         0U
/** @} */

/** @defgroup Timing_Constants
 * @{
 */
#define CONTROL_LOOP_DELAY          100U            /* milliseconds */
#define SYSTEM_TICK_FREQUENCY       1000U           /* Hz */
/** @} */

/* ============================================================================
 * Type Definitions
 * ========================================================================== */

/**
 * @brief Motor control structure for differential drive
 */
typedef struct {
    uint16_t left_pwm;              /*!< Left motor PWM duty cycle (0-1000) */
    uint16_t right_pwm;             /*!< Right motor PWM duty cycle (0-1000) */
    int16_t left_velocity;          /*!< Left wheel velocity estimate */
    int16_t right_velocity;         /*!< Right wheel velocity estimate */
} MotorControl_TypeDef;

/**
 * @brief Robot state machine
 */
typedef enum {
    ROBOT_STATE_INIT = 0,           /*!< Initialization state */
    ROBOT_STATE_IDLE,               /*!< Idle, waiting for commands */
    ROBOT_STATE_MOVING,             /*!< Active motion */
    ROBOT_STATE_ERROR               /*!< Error state */
} RobotState_TypeDef;

/* ============================================================================
 * Public Function Prototypes
 * ========================================================================== */

/**
 * @brief Error handler for critical failures
 *
 * This function is called when a hardware initialization or runtime error
 * is detected. It disables interrupts and enters an infinite loop while
 * blinking the status LED.
 */
void Error_Handler(void);

/**
 * @brief Non-Maskable Interrupt Handler
 */
void NMI_Handler(void);

/**
 * @brief Hard Fault Exception Handler
 */
void HardFault_Handler(void);

/**
 * @brief Memory Management Fault Handler
 */
void MemManage_Handler(void);

/**
 * @brief Bus Fault Exception Handler
 */
void BusFault_Handler(void);

/**
 * @brief Usage Fault Exception Handler
 */
void UsageFault_Handler(void);

/**
 * @brief Supervisor Call Handler
 */
void SVC_Handler(void);

/**
 * @brief Debug Monitor Handler
 */
void DebugMon_Handler(void);

/**
 * @brief Pending Service Call Handler
 */
void PendSV_Handler(void);

/**
 * @brief System Tick Timer Handler
 */
void SysTick_Handler(void);

/**
 * @brief HAL Initialization Hook
 *
 * Called by HAL_Init() to perform system initialization.
 * This can be overridden in application code if needed.
 */
void HAL_MspInit(void);

/**
 * @brief Timer PWM Mode MSP Initialization
 *
 * Called by HAL_TIM_PWM_Init() to initialize Timer-specific hardware.
 *
 * @param htim Pointer to TIM_HandleTypeDef structure
 */
void HAL_TIM_PWM_MspInit(TIM_HandleTypeDef *htim);

/* ============================================================================
 * Extern Declarations
 * ========================================================================== */

/** System clock frequency in Hz */
extern uint32_t SystemCoreClock;

/* ============================================================================
 * Assertion Macro
 * ========================================================================== */

/**
 * @brief Assert macro for debugging
 *
 * In debug builds, asserts that a condition is true.
 * In release builds, this macro is empty.
 */
#ifdef DEBUG
    #define ASSERT(expr) \
        if (!(expr)) { \
            Error_Handler(); \
        }
#else
    #define ASSERT(expr)
#endif

/* ============================================================================
 * C++ Support
 * ========================================================================== */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
