# Energy Market Simulation

A multi-process energy market simulation built in Python to demonstrate advanced Inter-Process Communication (IPC) mechanisms including shared memory, message queues, sockets, and semaphores.

## Overview

This project simulates a dynamic energy market ecosystem where multiple autonomous processes communicate and synchronize to create a realistic energy trading environment. The simulation was developed as part of a concurrency and parallelism curriculum to explore various IPC patterns and synchronization primitives.

## Architecture

The simulation consists of four main process types that communicate through different IPC mechanisms:

### Core Processes

1. **Market Process** (`market.py`)
   - Central energy trading hub using TCP sockets
   - Dynamic pricing algorithm based on supply/demand and external factors
   - Thread pool executor for concurrent transaction handling
   - Synchronization using semaphores and locks

2. **Home Processes** (`home.py`)
   - Multiple autonomous home instances with different energy profiles
   - Three trading policies: GIVE_ONLY, SELL_ONLY, SELL_IF_NONE
   - Peer-to-peer energy sharing via message queues
   - Market transactions via socket connections

3. **Weather Process** (`weather.py`)
   - Simulates temperature fluctuations affecting energy consumption
   - Uses shared memory (multiprocessing.Value) for real-time data sharing
   - Impacts home energy consumption patterns

4. **External Events Process** (`external.py`)
   - Simulates random external events (wars, fuel shortages)
   - Uses UNIX signals (SIGUSR1, SIGUSR2) for event notification
   - Affects market energy pricing dynamically

## IPC Mechanisms Implemented

- **Sockets**: TCP connections between homes and market for transactions
- **Message Queues**: SysV IPC message queues for home-to-home energy sharing
- **Shared Memory**: Multiprocessing Value for weather data sharing
- **Semaphores**: Process synchronization and resource limiting
- **Signals**: External event notification system
- **Locks**: Thread-safe transaction processing

## Key Features

### Dynamic Pricing Algorithm
Energy prices fluctuate based on:
- Temperature (affects consumption)
- Supply/demand balance
- External events (war, fuel shortage)
- Historical pricing with decay factor (GAMMA = 0.75)

### Home Energy Policies
- **GIVE_ONLY**: Share surplus energy with other homes, never sell to market
- **SELL_ONLY**: Always sell surplus directly to market
- **SELL_IF_NONE**: Try sharing first, sell to market if no takers

### Synchronization Patterns
- Barrier synchronization ensures all processes complete each tick
- Custom message queue-based counters for distributed synchronization
- Producer-consumer patterns for energy surplus/deficit matching

## Project Structure

```
├── main.py           # Main simulation orchestrator
├── market.py         # Market process and pricing logic
├── home.py          # Home process with energy management
├── weather.py       # Weather simulation affecting consumption
├── external.py      # External events (war, fuel shortage)
└── utility.py       # Custom synchronization primitives
```

## How It Works

1. **Initialization**: Main process spawns weather, market, and multiple home processes
2. **Tick-based Simulation**: Each time step follows this sequence:
   - Weather updates temperature (affects consumption)
   - Homes calculate energy delta (production - consumption)
   - Homes attempt peer-to-peer energy sharing via message queues
   - Remaining surplus/deficit traded with market via sockets
   - Market updates pricing based on transactions and external events
3. **Synchronization**: All processes synchronize at tick boundaries using semaphores

## Running the Simulation

```bash
python main.py
```

The simulation runs indefinitely, printing real-time information about:
- Current temperature
- Home energy deltas and trading policies
- Market transactions and pricing
- External events

## Technical Highlights

- **Process Safety**: All shared resources protected by appropriate synchronization primitives
- **Scalability**: Configurable number of homes and market transaction limits
- **Fault Tolerance**: Proper cleanup of IPC resources on termination
- **Real-time Simulation**: Tick-based time progression with configurable duration

## Learning Objectives Achieved

- Implementation of multiple IPC mechanisms in a single application
- Understanding of process synchronization and coordination
- Experience with concurrent programming patterns
- Real-world application of theoretical concurrency concepts

This project demonstrates practical application of operating systems concepts in a complex, multi-process environment that mimics real-world distributed systems challenges.
