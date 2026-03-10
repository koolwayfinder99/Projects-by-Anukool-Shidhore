/**
 * @file main.c
 * @brief STM32F4 Motor Control for Differential Drive Robot
 * @author Robotics Team
 * @date 2026
 *
 * This file implements PWM-based motor control for a differential drive robot
 * using STM32F4 microcontroller with HAL (Hardware Abstraction Layer).
 * Two PWM channels on Timer 1 drive left and right motors independently.
 */

#include "main.h"

/* Private variables */
static TIM_HandleTypeDef htim1;  /* Timer 1 handle for PWM generation */

/* Private function prototypes */
static void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_TIM1_PWM_Init(void);

/**
 * @brief System Clock Configuration
 *
 * Configures the system clock to run at maximum frequency for STM32F4.
 * Sets up PLL, AHB, APB1, and APB2 prescalers.
 */
static void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    /* Enable Power Control clock */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    /* Initialize the RCC Oscillators according to the specified parameters */
    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    RCC_OscInitStruct.HSEState = RCC_HSE_ON;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    RCC_OscInitStruct.PLL.PLLM = 8;
    RCC_OscInitStruct.PLL.PLLN = 336;
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
    RCC_OscInitStruct.PLL.PLLQ = 7;

    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    /* Initialize the CPU, AHB and APB buses clocks */
    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                                   RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
    RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
    {
        Error_Handler();
    }
}

/**
 * @brief GPIO Initialization
 *
 * Configures GPIO pins for LED indicators and button inputs.
 * Enables GPIOA, GPIOB, and GPIOC clocks.
 */
static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    /* Enable GPIO Clocks */
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* Configure GPIO pins for LED (PA5 as example) */
    GPIO_InitStruct.Pin = GPIO_PIN_5;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

    /* Initialize LED to OFF */
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_5, GPIO_PIN_RESET);
}

/**
 * @brief Timer 1 PWM Mode Initialization
 *
 * Configures Timer 1 for PWM generation on two channels (CH1 and CH2).
 * Timer clock: 84 MHz (from APB2)
 * Prescaler: 83 (divides clock to 1 MHz)
 * Period: 1000 (gives 1 kHz PWM frequency)
 * PWM duty cycle can be set via __HAL_TIM_SET_COMPARE()
 *
 * PA8 (TIM1_CH1) - Left Motor PWM
 * PA9 (TIM1_CH2) - Right Motor PWM
 */
static void MX_TIM1_PWM_Init(void)
{
    TIM_OC_InitTypeDef sConfigOC = {0};
    TIM_BreakDeadTimeConfigTypeDef sBreakDeadTimeConfig = {0};

    /* Enable Timer 1 Clock */
    __HAL_RCC_TIM1_CLK_ENABLE();

    /* Initialize Timer 1 base */
    htim1.Instance = TIM1;
    htim1.Init.Prescaler = 83;          /* 84MHz / 84 = 1 MHz */
    htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim1.Init.Period = 1000;           /* 1000 counts = 1 kHz frequency */
    htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter = 0;
    htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    if (HAL_TIM_PWM_Init(&htim1) != HAL_OK)
    {
        Error_Handler();
    }

    /* Configure PWM Output Compare for Channel 1 (Left Motor) */
    sConfigOC.OCMode = TIM_OCMODE_PWM1;
    sConfigOC.Pulse = 500;              /* 50% duty cycle (500/1000) */
    sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
    sConfigOC.OCNPolarity = TIM_OCNPOLARITY_HIGH;
    sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
    sConfigOC.OCIdleState = TIM_OCIDLESTATE_RESET;
    sConfigOC.OCNIdleState = TIM_OCNIDLESTATE_RESET;

    if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
    {
        Error_Handler();
    }

    /* Configure PWM Output Compare for Channel 2 (Right Motor) */
    if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
    {
        Error_Handler();
    }

    /* Configure Break and Dead Time */
    sBreakDeadTimeConfig.OffStateRunMode = TIM_OSSR_ENABLE;
    sBreakDeadTimeConfig.OffStateIDLEMode = TIM_OSSI_ENABLE;
    sBreakDeadTimeConfig.LockLevel = TIM_LOCKLEVEL_OFF;
    sBreakDeadTimeConfig.DeadTime = 0;
    sBreakDeadTimeConfig.BreakState = TIM_BREAK_DISABLE;
    sBreakDeadTimeConfig.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
    sBreakDeadTimeConfig.BreakFilter = 0;
    sBreakDeadTimeConfig.Break2State = TIM_BREAK2_DISABLE;
    sBreakDeadTimeConfig.Break2Polarity = TIM_BREAKPOLARITY_HIGH;
    sBreakDeadTimeConfig.Break2Filter = 0;
    sBreakDeadTimeConfig.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;

    if (HAL_TIMEx_ConfigBreakDeadTime(&htim1, &sBreakDeadTimeConfig) != HAL_OK)
    {
        Error_Handler();
    }

    /* Start PWM on both channels */
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
}

/**
 * @brief Main application entry point
 *
 * Initializes the microcontroller hardware and runs the main control loop.
 * The differential drive robot operates with both motors at 50% duty cycle
 * for testing. In production, these values would be controlled by a PID loop
 * or higher-level navigation system.
 *
 * @return int Exit status (never returns in this embedded application)
 */
int main(void)
{
    /* Initialize HAL */
    HAL_Init();

    /* Configure system clock */
    SystemClock_Config();

    /* Initialize GPIO */
    MX_GPIO_Init();

    /* Initialize Timer 1 for PWM */
    MX_TIM1_PWM_Init();

    /* Main control loop */
    while (1)
    {
        /* Set both motors to 50% duty cycle (500 out of 1000) */
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 500);  /* Left motor */
        __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 500);  /* Right motor */

        /* Toggle LED indicator */
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);

        /* 100ms delay for control loop timing */
        HAL_Delay(100);
    }

    return 0;
}

/**
 * @brief HAL MSP Initialization Hook
 *
 * This function is called by HAL_Init() to perform MSP (MCU Support Package)
 * initialization. It configures low-level hardware like clock and GPIO.
 */
void HAL_MspInit(void)
{
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();
}

/**
 * @brief Timer MSP Initialization
 *
 * Called by HAL_TIM_PWM_Init() to configure Timer-specific hardware settings.
 * Handles GPIO alternate function configuration for PWM outputs.
 */
void HAL_TIM_PWM_MspInit(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM1)
    {
        GPIO_InitTypeDef GPIO_InitStruct = {0};

        /* Enable GPIO Clock for Port A */
        __HAL_RCC_GPIOA_CLK_ENABLE();

        /* Configure PA8 (TIM1_CH1) and PA9 (TIM1_CH2) as alternate function */
        GPIO_InitStruct.Pin = GPIO_PIN_8 | GPIO_PIN_9;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_NOPULL;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
        GPIO_InitStruct.Alternate = GPIO_AF1_TIM1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
    }
}

/**
 * @brief Error Handler
 *
 * Called when an error condition is detected during hardware initialization.
 * Enters infinite loop with LED blinking for visual indication.
 */
void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
        HAL_GPIO_TogglePin(GPIOA, GPIO_PIN_5);
        HAL_Delay(100);
    }
}

/**
 * @brief NMI Handler
 */
void NMI_Handler(void)
{
}

/**
 * @brief Hard Fault Handler
 */
void HardFault_Handler(void)
{
    while (1)
    {
    }
}

/**
 * @brief Memory Management Fault Handler
 */
void MemManage_Handler(void)
{
    while (1)
    {
    }
}

/**
 * @brief Bus Fault Handler
 */
void BusFault_Handler(void)
{
    while (1)
    {
    }
}

/**
 * @brief Usage Fault Handler
 */
void UsageFault_Handler(void)
{
    while (1)
    {
    }
}

/**
 * @brief SVCall Handler
 */
void SVC_Handler(void)
{
}

/**
 * @brief Debug Monitor Handler
 */
void DebugMon_Handler(void)
{
}

/**
 * @brief PendSV Handler
 */
void PendSV_Handler(void)
{
}

/**
 * @brief System Tick Timer Handler
 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
