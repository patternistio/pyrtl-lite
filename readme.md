# pyrtl-lite: Practical Usage Guide

This guide shows how to build small hardware-style models with `pyrtlite.py`.
The library is minimal, so most workflows are short and explicit.

## 1. Mental Model

A design is a tree of `Module` objects.
Each module defines:

- signals (`In`, `Out`, `Wire`, `Reg`)
- combinational equations (`@=`)
- sequential updates (`<<=` on registers)

Simulation is cycle-based:

1. gather drivers from `logic()`
2. settle combinational network
3. compute register next values
4. commit register values on clock step

## 2. Import and First Example

```python
from pyrtlite import *

class Adder(Module):
    def build(self):
        self.a = In(0)
        self.b = In(0)
        self.y = Out(0)

    def logic(self):
        self.y @= self.a + self.b

top = Adder()
sim = Sim(top)

sim.poke(top.a, 7)
sim.poke(top.b, 5)
sim.settle()
print(sim.peek(top.y))  # 12
```

Use `settle()` to evaluate combinational logic without advancing a cycle.

## 3. Signal Types

Constructors:

- `In(init=0)` input-like signal
- `Out(init=0)` output-like signal
- `Wire(init=0)` internal combinational signal
- `Reg(init=0)` state-holding register

All signals are expressions, so you can use operators directly.

## 4. Assignment Rules

### 4.1 Combinational: `@=`

Drive wires/outputs with expressions:

```python
self.sum @= self.a + self.b
self.gt @= self.a > self.b
```

Rules:

- one combinational driver per signal
- do not combinationally drive a register

### 4.2 Sequential: `<<=`

Drive register next value:

```python
self.acc <<= self.acc + self.input_val
```

`self.acc` changes when `sim.step()` commits.

### 4.3 Scheduled Value: `.nxt`

`reg.nxt` is an expression for the scheduled next value:

```python
self.predicted @= self.counter.nxt
```

Useful for look-ahead combinational logic.

## 5. Expressions and Operators

Supported expression styles include:

- arithmetic: `+`, `-`, `*`, `/`, `//`, `%`
- bitwise style: `&`, `|`, `^`, `~`
- comparison: `<`, `<=`, `>`, `>=`, `==`, `!=`
- unary: `-x`, `~x`

Constants auto-lift:

```python
self.y @= self.x + 42
```

Compound expression example:

```python
self.out @= ((self.a + 1) * (self.b - 2)) % 16
```

## 6. Mux (Conditional Select)

Use `Mux(cond, a, b)`:

```python
self.out @= Mux(self.sel, self.path0, self.path1)
```

- if `cond` is true, choose `a`
- else choose `b`

## 7. Building Modules

Standard pattern:

```python
class Counter(Module):
    def build(self, width=8):
        self.en = In(1)
        self.q = Out(0)
        self.r = Reg(0)
        self.width = width

    def logic(self):
        self.r <<= Mux(self.en, (self.r + 1) % (1 << self.width), self.r)
        self.q @= self.r
```

Guidelines:

- declare all interface/internal signals in `build()`
- keep `logic()` pure wiring/updates
- store submodules as attributes on `self` for hierarchy

## 8. Vectors and Arrays

`Vec(shape, proto)` deep-copies a prototype into a nested list.

```python
self.lanes = Vec(4, Reg(0))
self.grid = Vec((2, 3), Wire(0))
```

Tips:

- integer shape gives one-dimensional list
- tuple shape gives nested lists
- prototype can be signal, module, or any Python object

## 9. Memory

`Mem(depth, init=0)` is modeled as a register-backed array.

```python
self.mem = Mem(depth=8, init=0)
```

Access patterns:

- read: `self.mem[addr]` or `self.mem.read(addr)`
- write next state: `self.mem[addr] <<= value`

Tiny RAM example:

```python
class TinyRAM(Module):
    def build(self):
        self.addr = In(0)
        self.din = In(0)
        self.we = In(0)
        self.dout = Out(0)
        self.mem = Mem(8, init=0)

    def logic(self):
        self.dout @= self.mem[self.addr]
        self.mem[self.addr] <<= Mux(self.we, self.din, self.mem[self.addr])
```

## 10. Simulator API

Create simulator:

```python
sim = Sim(top)
```

Most-used methods:

- `sim.poke(sig, value)` set a signal value
- `sim.peek(sig)` read a signal value
- `sim.settle(trace=False)` run combinational settle only
- `sim.step(n=1, trace=False)` advance cycles
- `sim.run(n, trace=False)` alias of `step`
- `sim.until(pred, max_cycles=1000)` run until predicate true
- `sim.state(include_inputs=True)` list of `(name, value)`
- `sim.dump()` print current state

Combinational probe pattern:

```python
sim.poke(top.a, 3)
sim.poke(top.b, 4)
sim.settle()
print(sim.peek(top.y))
```

Sequential loop pattern:

```python
for cyc in range(5):
    sim.poke(top.en, 1)
    sim.step()
    print(cyc, sim.peek(top.q))
```

## 11. Assertions

Use module-level assertions during `logic()`:

```python
def logic(self):
    self.y @= self.a + self.b
    self.Assert(self.y >= 0, "y became negative")
```

If false, simulation raises `AssertionError` with module path.

## 12. End-to-End Example

```python
from pyrtlite import *

class UpDownCounter(Module):
    def build(self):
        self.en = In(1)
        self.up = In(1)
        self.q = Out(0)
        self.r = Reg(0)

    def logic(self):
        delta = Mux(self.up, 1, -1)
        self.r <<= Mux(self.en, self.r + delta, self.r)
        self.q @= self.r
        self.Assert(self.q > -1000, "counter runaway")

top = UpDownCounter()
sim = Sim(top)

sim.poke(top.en, 1)
sim.poke(top.up, 1)
sim.step(3)
print("after count up:", sim.peek(top.q))

sim.poke(top.up, 0)
sim.step(2)
print("after count down:", sim.peek(top.q))
```

## 13. Debugging Checklist

- call `sim.dump()` after `settle()` or `step()`
- use `trace=True` for transition logs
- inspect `sim.state()` for programmatic checks
- verify each signal/register has one driver
- test a module in isolation before composing hierarchy

## 14. Notes for This Snapshot

The library is intentionally lightweight and appears to be in-progress.
If behavior looks off, inspect `pyrtlite.py` and patch locally.
In practice, tiny local fixes are often enough for examples.

## 15. Fast Workflow

1. define interface in `build()`
2. add minimal `logic()`
3. test combinational behavior with `settle()`
4. test sequential behavior with `step()`
5. add assertions for invariants
6. expand with `Vec`, `Mem`, and submodules

That is the full practical surface area needed to use `pyrtl-lite` for small models and experiments.
