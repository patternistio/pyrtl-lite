pyrtl lite is a hdlish python dsl made to speed up hardware development. 

hardware is specified using `Module` objects as follows

```python
from pyrtlite import *              # pyrtl lite is a one file library

class Foo(Module):                  # hardware inherits from module
    def build(self):                # declare signals in build()
        self.a = In(0)              # inputs arent driven internally
        self.b = Reg(0)             # registers are sequentially driven
        self.c = Wire(0)            # wires are combinationally driven
        self.d = Out(0)             # outputs are combinationally driven

    def logic(self):                # declare all logic in logic()
        self.b <<= self.a           # sequential assignment uses <<=
        self.d @= self.b            # combinational assignment uses @=
```

and can then be simulated using `Sim` 

```python
sim = Sim(Foo)                      # create sim with Sim()

sim.poke(sig, val)                  # set signal value 
sim.peek(sig)                       # read signal value
sim.settle(trace)                   # combinational settle
sim.step(n, trace)                  # advance by n cycles
sim.run(n, trace)                   # alias of step
sim.until(cond, max_cycles)         # run until cond is true
sim.state(include_inputs)           # list out (name, value)
sim.dump()                          # print out current state
```

pyrtl lite also contains a few special objects

```python
self.bus = Vec(n, In(0))            # creates array of length n
self.grid = Vec((n, m), Reg(0))     # creates a (n, m) matrix
output = self.bus.to_list()         # converts any vector to a list

self.mem = Mem(depth, init)         # register array with depth
self.mem.read(addr)                 # read value at addr in mem
self.mem.write(addr, val)           # write value to addr in mem

self.out &= Mux(cond, a, b)         # if cond choose a else b
self.Assert(cond, msg)              # mmodule level assertion
``` 

behind the scenes, combinational expressions are compiled into a lazy evaluation graph and signals hold values between sim steps. each simulation cycle, the simulator builds logic, performs a combinational settle, evaluates the next sequential state, commits, and then performs another combinational settle. 

the library is intentionally minimal and easy to modify. please add more features!