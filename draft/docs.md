# Tiny Hardware-Style Python Simulator

Short reference for `sim.py`.

## Model
- `@=`: combinational drive. Example: `out @= a + b`
- `<<=`: register next-state. Example: `count <<= count + 1`
- `settle()`: run combinational logic now
- `step()`: evaluate logic, commit registers, re-settle outputs

## Signals
- `In(x)`: input port. Example: `en = In(False)`
- `Out(x)`: output port. Example: `out = Out(0)`
- `Wire(x)`: combinational temporary. Example: `tmp = Wire(0)`
- `Reg(x)`: state element. Example: `acc = Reg(0)`
- Rule: only non-registers accept `@=`; only registers accept `<<=`

## Expressions
- Signals are expressions, so `+ - * / // % & | ^ < <= > >= == !=` all work
- Example: `flag @= (x > 3) & (x != 7)`
- Example: `neg @= -x`; `bits @= ~x`
- `Mux(cond, a, b)`: conditional value. Example: `out @= Mux(sel, left, right)`
- `reg.nxt`: scheduled next value of a register. Example: `mem[addr] <<= regs[0].nxt`

## Modules
- Subclass `Module`, create signals in `build(...)`, describe behavior in `logic()`

```python
from sim import Module, In, Out, Reg

class Counter(Module):
    def build(self):
        self.en = In(False); self.count = Reg(0); self.out = Out(0)
    def logic(self):
        self.count <<= self.count + 1 if self.en else self.count
        self.out @= self.count
```

- Modules can contain child modules, vectors, bundles, lists, and memories
- `Assert(cond, msg)`: stop simulation on bad states. Example: `self.Assert(self.count >= 0, "bad count")`

## Structured data
- `Vec(n, proto)`: arrays. Example: `regs = Vec(8, Reg(0))`
- `Vec((r, c), proto)`: nested arrays. Example: `m = Vec((2, 3), Reg(0))`
- `Bundle`: named groups of fields

```python
from sim import Bundle, In
class Pair(Bundle):
    def __init__(self):
        self.left = In(0); self.right = In(0)
```

- `Mem(depth, init)`: indexed register-backed storage
- Example: `mem = Mem(16, 0)`; `word = mem[3]`; `mem.write(3, 99)`

## Simulation API

```python
from sim import Sim, poke, peek
top = Counter(); sim = Sim(top)
poke(top.en, True); sim.step(); print(peek(top.out))
```

- `sim.poke(sig, value)` / `poke(sig, value)`: write current value directly
- `sim.peek(sig)` / `peek(sig)`: read current value
- `sim.settle(trace=False)`: run combinational logic without advancing time
- `sim.step(n=1, trace=False)`: advance cycles
- `sim.run(n, trace=False)`: alias for `step(n)`
- `sim.until(pred, max_cycles=1000, trace=False)`: run until `pred()` is true
- `sim.state(include_inputs=True)`: list of `(name, value)` pairs
- `sim.dump(include_inputs=True)`: print current state
- `sim.changed()`: last non-empty change wave

## Tracing and debug
- `sim.watch(sig1, sig2, ...)`: limit traced output to selected signals
- `sim.unwatch()`: clear watchlist
- Example: `sim.watch(top.count, top.out).step(trace=True)`

## Behavior notes
- One combinational driver per non-register signal
- One sequential driver per register each cycle
- Parent modules can wire child inputs and children can define internal logic
- Input ports may also be combinationally driven by parents
- If settle does not converge within `max_settle`, `Sim` raises `RuntimeError`
